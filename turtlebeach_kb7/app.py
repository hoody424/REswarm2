"""
Turtle Beach Command Series KB7 - Unified Desktop Controller.

Main desktop application combining:
  1. Universal Windows Sound Mixer (per-app volume faders across all devices)
  2. Procedural Display Theme & Wallpaper Manager (live preview & 1-click upload)
  3. Widget & Page Layout Configurator
  4. Hardware Daemon & Real-time Touch Event Monitor
"""

import sys
import os
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image, ImageTk

from .audio_mixer import UniversalAudioMixer, AppGroup, AudioDeviceItem
from .client import KB7Client
from .daemon import KB7Daemon
from .theme_generator import THEME_PRESETS
from .image import convert_to_rgb565
from .widgets import WIDGET_CATALOG, LAYOUT_TEMPLATES, lookup_widget
from .device import KB7Device, SLOT_BACKGROUND
from .steelseries import SteelSeriesSync, THEME_RGB_MAP
from .lighting import (
    LightingEngine,
    LIGHTING_EFFECTS,
    COLOR_PALETTES,
    rgb_to_hex,
    hex_to_rgb,
    ZONE_WASD,
    ZONE_ARROWS,
    ZONE_F_KEYS,
)
from .streamdeck import (
    SmartStreamDeckManager,
    STREAMDECK_ACTIONS,
    STREAMDECK_PROFILES,
    DetectedStreamWindow,
    scan_stream_windows,
    focus_window_by_hwnd,
    capture_screen_snapshot_for_kb7,
)

# Design Palette
COLOR_BG_DARK = "#0d1117"
COLOR_BG_CARD = "#161b22"
COLOR_BG_HOVER = "#21262d"
COLOR_ACCENT = "#00d2ff"       # Cyan
COLOR_ACCENT_ALT = "#ffaa00"   # Amber Gold
COLOR_TEXT_MAIN = "#f0f6fc"
COLOR_TEXT_MUTED = "#8b949e"
COLOR_MUTE_ACTIVE = "#f85149"  # Red
COLOR_MUTE_INACTIVE = "#21262d"
COLOR_BORDER = "#30363d"
COLOR_TAB_ACTIVE = "#1f242c"


class KB7CommandCenterApp:
    """
    Unified GUI Controller for Turtle Beach KB7.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Turtle Beach KB7 - Command Center & Sound Mixer")
        self.root.geometry("980x660")
        self.root.minsize(860, 580)
        self.root.configure(bg=COLOR_BG_DARK)

        # Set application icon if present
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "kb7_app.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # Audio Mixer Engine
        self.mixer = UniversalAudioMixer()
        self.active_device: Optional[AudioDeviceItem] = None
        self.app_groups: List[AppGroup] = []
        self.selected_target = "Master"
        self.app_widgets: Dict[str, Dict[str, Any]] = {}
        self.is_dragging = False

        # Hardware & Daemon Connection
        self.daemon: Optional[KB7Daemon] = None
        self.client: Optional[KB7Client] = None
        self.hw_connected = False
        self.running = True
        self.active_tab = "streamdeck"

        # SteelSeries Mouse RGB Synchronization
        self.steelseries: Optional[SteelSeriesSync] = SteelSeriesSync()

        # Theme & Wallpaper State
        self.selected_theme_name = "tactical_hud"
        self.preview_image_tk: Optional[ImageTk.PhotoImage] = None
        self.custom_image_path: Optional[str] = None

        # Smart Stream Deck Engine
        self.streamdeck = SmartStreamDeckManager()
        self.selected_sd_slot: int = 0
        self._last_touch_time: float = 0.0

        # Customizable RGB Lighting Engine (KB7 7-Zone Planar RGB + SteelSeries Mouse)
        self.lighting = LightingEngine(
            hw_apply_callback=self._send_kb7_lighting_hw,
            steelseries=self.steelseries,
        )

        # Build Navigation & Main Views immediately so the window opens in < 0.1s
        self._build_header()
        self._build_tabs()
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()

        # Non-blocking background initialization of hardware daemon, SteelSeries, lighting & audio
        threading.Thread(target=self._async_init_services, daemon=True).start()
        self._start_background_workers()

    def _async_init_services(self):
        """Initializes USB HID daemon, SteelSeries GameSense, lighting & audio without blocking the GUI."""
        self._ensure_hardware_service()
        if self.hw_connected:
            self.root.after(0, lambda: self.lbl_hw_status.configure(text="● HARDWARE CONNECTED", fg=COLOR_ACCENT))
        if self.steelseries:
            try:
                self.steelseries.start()
                if self.steelseries.connected and hasattr(self, "lbl_ss_status"):
                    self.root.after(0, lambda: self.lbl_ss_status.configure(text="● SteelSeries Aerox 3 verbunden", fg="#00e575"))
            except Exception as e:
                print(f"[!] SteelSeries init warning: {e}")

        self.lighting.start()
        self.refresh_audio_state()
        self.root.after(200, self.refresh_display_settings)
        self.root.after(400, self.refresh_slots_view)

    def _ensure_hardware_service(self):
        """Connects to daemon or starts in-process single-writer service."""
        try:
            self.client = KB7Client()
            if self.client.connect(timeout=0.4):
                self.hw_connected = True
                print("[+] Connected to existing KB7 Daemon.")
            else:
                raise ConnectionError()
        except Exception:
            # Launch in-process daemon
            try:
                self.daemon = KB7Daemon()
                self.daemon.start()
                time.sleep(0.3)
                self.client = KB7Client()
                self.client.connect()
                self.hw_connected = True
                print("[+] Started integrated KB7 Daemon service.")
            except Exception as e:
                print(f"[!] Hardware daemon startup warning: {e}")
                self.hw_connected = False

        if self.client and self.hw_connected:
            @self.client.on_touch()
            def on_touch(ev):
                self._handle_touch_event(ev)

    def _handle_touch_event(self, ev: Dict[str, Any]):
        """Logs and handles touch events from the display, including Smart Stream Deck actions."""
        gesture = ev.get("gesture")
        slot = ev.get("slot_id")
        line = f"[{time.strftime('%H:%M:%S')}] Touch: {gesture:<11} | Slot={slot:2d} | Coord=({ev.get('x')}, {ev.get('y')})"
        self.root.after(0, lambda: self._append_log(line))

        # Trigger Smart Stream Deck host action when a tile (0..11) is tapped on the KB7 screen
        if gesture in ("tap", "up") and isinstance(slot, int) and 0 <= slot < 12:
            now = time.time()
            if now - self._last_touch_time > 0.35 and getattr(self, "var_sd_touch_bridge", None) and self.var_sd_touch_bridge.get():
                self._last_touch_time = now
                self.root.after(0, lambda s=slot: self._trigger_streamdeck_slot(s, from_hw=True))

    def _build_header(self):
        """Top Brand Header Bar."""
        header = tk.Frame(self.root, bg=COLOR_BG_CARD, height=54, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        header.pack(fill=tk.X, side=tk.TOP, padx=12, pady=(10, 4))

        title_box = tk.Frame(header, bg=COLOR_BG_CARD)
        title_box.pack(side=tk.LEFT, padx=16, pady=8)

        lbl_logo = tk.Label(title_box, text="TURTLE BEACH // COMMAND KB7", font=("Segoe UI", 12, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD)
        lbl_logo.pack(anchor="w")

        lbl_sub = tk.Label(title_box, text="Unified Hardware Controller, Display Themes & Sound Mixer", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        lbl_sub.pack(anchor="w")

        # Status badge
        self.lbl_hw_status = tk.Label(
            header,
            text="● HARDWARE CONNECTED" if self.hw_connected else "○ HARDWARE OFFLINE",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_ACCENT if self.hw_connected else COLOR_TEXT_MUTED,
            bg=COLOR_BG_CARD, padx=14
        )
        self.lbl_hw_status.pack(side=tk.RIGHT, padx=16)

    def _build_tabs(self):
        """Modern Tab Navigation & Containers."""
        tab_nav = tk.Frame(self.root, bg=COLOR_BG_DARK)
        tab_nav.pack(fill=tk.X, padx=12, pady=(2, 4))

        self.tab_buttons: Dict[str, tk.Button] = {}
        self.tab_frames: Dict[str, tk.Frame] = {}

        tabs = [
            ("mixer", "🔊 Sound Mixer"),
            ("streamdeck", "🎛️ Smart Stream Deck"),
            ("lighting", "💡 Leuchteffekte & RGB"),
            ("themes", "🎨 Display Themes"),
            ("widgets", "🧩 Widgets & Pages"),
            ("hardware", "⚡ Hardware & Touch"),
        ]

        self.content_container = tk.Frame(self.root, bg=COLOR_BG_DARK)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        for key, title in tabs:
            btn = tk.Button(
                tab_nav, text=title, font=("Segoe UI", 9, "bold"),
                bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, bd=0, padx=13, pady=8,
                cursor="hand2", activebackground=COLOR_BG_HOVER, activeforeground=COLOR_TEXT_MAIN,
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.tab_buttons[key] = btn

            frame = tk.Frame(self.content_container, bg=COLOR_BG_DARK)
            self.tab_frames[key] = frame

        # Build individual views
        self._build_mixer_tab(self.tab_frames["mixer"])
        self._build_streamdeck_tab(self.tab_frames["streamdeck"])
        self._build_lighting_tab(self.tab_frames["lighting"])
        self._build_themes_tab(self.tab_frames["themes"])
        self._build_widgets_tab(self.tab_frames["widgets"])
        self._build_hardware_tab(self.tab_frames["hardware"])

        self.switch_tab("streamdeck")

    def switch_tab(self, active_key: str):
        """Switches active view."""
        self.active_tab = active_key
        for key, frame in self.tab_frames.items():
            if key == active_key:
                frame.pack(fill=tk.BOTH, expand=True)
                self.tab_buttons[key].configure(bg=COLOR_TAB_ACTIVE, fg=COLOR_ACCENT)
            else:
                frame.pack_forget()
                self.tab_buttons[key].configure(bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED)

        if active_key == "mixer":
            self.refresh_audio_state()
        elif active_key == "widgets":
            self.refresh_slots_view()

    # =========================================================================
    # TAB 1: AUDIO MIXER
    # =========================================================================

    def _build_mixer_tab(self, parent: tk.Frame):
        content = tk.Frame(parent, bg=COLOR_BG_DARK)
        content.pack(fill=tk.BOTH, expand=True)

        # Left: Master Card
        self.master_card = tk.Frame(content, bg=COLOR_BG_CARD, width=210, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.master_card.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=4)
        self.master_card.pack_propagate(False)

        lbl_m = tk.Label(self.master_card, text="MASTER OUTPUT", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD)
        lbl_m.pack(pady=(16, 2))

        self.lbl_master_dev = tk.Label(self.master_card, text="Default Device", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD, wraplength=180)
        self.lbl_master_dev.pack(pady=(0, 12))

        self.master_slider = tk.Scale(
            self.master_card, from_=100, to=0, orient=tk.VERTICAL,
            length=260, width=22, showvalue=False,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MAIN, troughcolor=COLOR_BG_DARK,
            activebackground=COLOR_ACCENT, highlightthickness=0, bd=0,
            command=self._on_master_slide
        )
        self.master_slider.pack(pady=4)

        self.lbl_master_pct = tk.Label(self.master_card, text="100%", font=("Segoe UI", 14, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        self.lbl_master_pct.pack(pady=4)

        self.btn_master_mute = tk.Button(
            self.master_card, text="MUTE", font=("Segoe UI", 9, "bold"),
            bg=COLOR_MUTE_INACTIVE, fg=COLOR_TEXT_MAIN, bd=0, padx=16, pady=6, cursor="hand2",
            command=self._toggle_master_mute
        )
        self.btn_master_mute.pack(pady=(6, 16))

        # Right: Application Channels Scroll Area
        apps_area = tk.Frame(content, bg=COLOR_BG_DARK)
        apps_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=4)

        lbl_apps_head = tk.Label(apps_area, text="ALL APPLICATION AUDIO CHANNELS", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK)
        lbl_apps_head.pack(anchor="w", padx=4, pady=(0, 4))

        self.canvas_mixer = tk.Canvas(apps_area, bg=COLOR_BG_DARK, bd=0, highlightthickness=0)
        self.sb_mixer = ttk.Scrollbar(apps_area, orient=tk.HORIZONTAL, command=self.canvas_mixer.xview)
        self.frame_mixer_scroll = tk.Frame(self.canvas_mixer, bg=COLOR_BG_DARK)

        self.frame_mixer_scroll.bind("<Configure>", lambda e: self.canvas_mixer.configure(scrollregion=self.canvas_mixer.bbox("all")))
        self.canvas_mixer.create_window((0, 0), window=self.frame_mixer_scroll, anchor="nw")
        self.canvas_mixer.configure(xscrollcommand=self.sb_mixer.set)

        self.canvas_mixer.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.sb_mixer.pack(fill=tk.X, side=tk.BOTTOM)

    def refresh_audio_state(self):
        """Dispatches an asynchronous audio state fetch to avoid blocking the GUI thread."""
        def fetch():
            try:
                import comtypes
                comtypes.CoInitialize()
            except Exception:
                pass
            try:
                dev = self.mixer.get_default_device()
                apps = self.mixer.get_grouped_apps()
                self.root.after(0, lambda d=dev, a=apps: self._apply_audio_state(d, a))
            except Exception:
                pass
        threading.Thread(target=fetch, daemon=True).start()

    def _apply_audio_state(self, dev, apps):
        """Applies audio updates in the Tkinter main thread in < 1ms."""
        self.active_device = dev
        self.app_groups = apps or []

        if self.active_device:
            self.lbl_master_dev.configure(text=self.active_device.name)
            if not self.is_dragging:
                v = self.active_device.volume
                self.master_slider.set(v)
                self.lbl_master_pct.configure(text=f"{v}%")

            if self.active_device.muted:
                self.btn_master_mute.configure(bg=COLOR_MUTE_ACTIVE, text="MUTED")
            else:
                self.btn_master_mute.configure(bg=COLOR_MUTE_INACTIVE, text="MUTE")

        # Update app cards
        current = set(a.name for a in self.app_groups)
        for dead in set(self.app_widgets.keys()) - current:
            self.app_widgets.pop(dead)["card"].destroy()

        for app in self.app_groups:
            if app.name not in self.app_widgets:
                self._create_app_card(app)
            else:
                self._update_app_card(app)

    def _create_app_card(self, app: AppGroup):
        card = tk.Frame(self.frame_mixer_scroll, bg=COLOR_BG_CARD, width=130, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        card.pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
        card.pack_propagate(False)

        lbl_name = tk.Label(card, text=app.name, font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD, wraplength=110)
        lbl_name.pack(pady=(12, 2))

        dev_badge = app.devices[0] if app.devices else "Audio Endpoint"
        lbl_dev = tk.Label(card, text=dev_badge[:16], font=("Segoe UI", 7), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        lbl_dev.pack(pady=(0, 8))

        slider = tk.Scale(
            card, from_=100, to=0, orient=tk.VERTICAL,
            length=200, width=18, showvalue=False,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MAIN, troughcolor=COLOR_BG_DARK,
            activebackground=COLOR_ACCENT, highlightthickness=0, bd=0,
            command=lambda v, a=app: self._on_app_slide(a, v)
        )
        slider.set(app.volume)
        slider.pack(pady=4)

        lbl_pct = tk.Label(card, text=f"{app.volume}%", font=("Segoe UI", 11, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        lbl_pct.pack(pady=2)

        btn_mute = tk.Button(
            card, text="MUTED" if app.muted else "MUTE", font=("Segoe UI", 8, "bold"),
            bg=COLOR_MUTE_ACTIVE if app.muted else COLOR_MUTE_INACTIVE, fg=COLOR_TEXT_MAIN,
            bd=0, padx=12, pady=4, cursor="hand2",
            command=lambda a=app: self._toggle_app_mute(a)
        )
        btn_mute.pack(pady=(4, 12))

        self.app_widgets[app.name] = {
            "card": card, "slider": slider, "lbl_pct": lbl_pct,
            "btn_mute": btn_mute, "lbl_dev": lbl_dev, "app": app
        }

    def _update_app_card(self, app: AppGroup):
        w = self.app_widgets.get(app.name)
        if not w:
            return
        w["app"] = app
        if not self.is_dragging:
            w["slider"].set(app.volume)
            w["lbl_pct"].configure(text=f"{app.volume}%")

        if app.muted:
            w["btn_mute"].configure(bg=COLOR_MUTE_ACTIVE, text="MUTED")
        else:
            w["btn_mute"].configure(bg=COLOR_MUTE_INACTIVE, text="MUTE")

    def _on_master_slide(self, val: str):
        self.is_dragging = True
        v = int(val)
        self.lbl_master_pct.configure(text=f"{v}%")
        if self.active_device:
            self.active_device.volume = v
        self.root.after(100, lambda: setattr(self, "is_dragging", False))

    def _on_app_slide(self, app: AppGroup, val: str):
        self.is_dragging = True
        v = int(val)
        w = self.app_widgets.get(app.name)
        if w:
            w["lbl_pct"].configure(text=f"{v}%")
        app.volume = v
        self.root.after(100, lambda: setattr(self, "is_dragging", False))

    def _toggle_master_mute(self):
        if self.active_device:
            self.active_device.toggle_mute()
            self.refresh_audio_state()

    def _toggle_app_mute(self, app: AppGroup):
        app.toggle_mute()
        self.refresh_audio_state()

    # =========================================================================
    # TAB 2: THEMES & WALLPAPER
    # =========================================================================

    def _build_themes_tab(self, parent: tk.Frame):
        content = tk.Frame(parent, bg=COLOR_BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, pady=4)

        # Left Column: Presets & Controls
        left = tk.Frame(content, bg=COLOR_BG_CARD, width=340, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        lbl_presets = tk.Label(left, text="DISPLAY THEMES & HUD PRESETS", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD)
        lbl_presets.pack(anchor="w", padx=16, pady=(12, 8))

        # Radio buttons for presets
        self.theme_var = tk.StringVar(value="matrix_cyberdeck")
        theme_presets_ui = [
            ("matrix_cyberdeck", "🟢 Matrix Cyberdeck", "Phosphor Green Code Rain & Terminal HUD"),
            ("toxic_radar", "🟢 Toxic Mech Radar", "Apex Tactical 360° Sonar & Honeycomb"),
            ("biohazard_reactor", "🟢 Biohazard Reactor", "Quantum Fusion Core & Radiant Plasma Conduits"),
            ("emerald_synthwave", "🟢 Emerald Synthwave", "Retro Wireframe Grid & Sliced Neon Sun"),
            ("tactical_hud", "🔷 Tactical Cockpit", "Cyberpunk Cyan & Gold Telemetry HUD"),
            ("audiophile_dark", "🔶 Audiophile Dark", "Studio Console & Golden VU Meters"),
            ("neon_cyberpunk", "🟣 Neon Cyberpunk", "Synthwave Magenta & Cyan Horizon"),
        ]
        for key, label, desc in theme_presets_ui:
            f_opt = tk.Frame(left, bg=COLOR_BG_CARD)
            f_opt.pack(fill=tk.X, padx=16, pady=2)

            rb = tk.Radiobutton(
                f_opt, text=label, variable=self.theme_var, value=key,
                font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
                selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
                command=self._on_theme_selected
            )
            rb.pack(anchor="w")

            lbl_d = tk.Label(f_opt, text=desc, font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
            lbl_d.pack(anchor="w", padx=20)

        # Custom File Button
        btn_custom = tk.Button(
            left, text="📁 Choose Custom Image File...", font=("Segoe UI", 9),
            bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=12, pady=5, cursor="hand2",
            command=self._browse_custom_image
        )
        btn_custom.pack(anchor="w", padx=16, pady=(8, 12))

        # Hardware Display Controls (Brightness, Timeout)
        tk.Label(left, text="HARDWARE SCREEN CONTROLS", font=("Segoe UI", 9, "bold"), fg=COLOR_ACCENT_ALT, bg=COLOR_BG_CARD).pack(anchor="w", padx=16, pady=(12, 4))

        # Brightness Slider
        f_bri = tk.Frame(left, bg=COLOR_BG_CARD)
        f_bri.pack(fill=tk.X, padx=16, pady=4)
        self.lbl_bri_val = tk.Label(f_bri, text="Brightness: 80%", font=("Segoe UI", 9), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        self.lbl_bri_val.pack(anchor="w")
        self.slider_brightness = ttk.Scale(f_bri, from_=0, to=100, orient=tk.HORIZONTAL, command=self._on_brightness_change)
        self.slider_brightness.set(80)
        self.slider_brightness.pack(fill=tk.X, pady=2)

        # Sleep Timeout Slider
        f_to = tk.Frame(left, bg=COLOR_BG_CARD)
        f_to.pack(fill=tk.X, padx=16, pady=4)
        self.lbl_to_val = tk.Label(f_to, text="Sleep Timeout: 60s", font=("Segoe UI", 9), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        self.lbl_to_val.pack(anchor="w")
        self.slider_timeout = ttk.Scale(f_to, from_=30, to=300, orient=tk.HORIZONTAL, command=self._on_timeout_change)
        self.slider_timeout.set(60)
        self.slider_timeout.pack(fill=tk.X, pady=2)

        # Right Column: Live 800x480 Preview & Upload Button
        right = tk.Frame(content, bg=COLOR_BG_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        lbl_prev_title = tk.Label(right, text="DISPLAY PREVIEW (480 x 800 PORTRAIT STRIDE)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        lbl_prev_title.pack(anchor="w", padx=20, pady=(16, 8))

        # Preview Image Frame
        self.lbl_preview = tk.Label(right, bg="#080c14", bd=0, highlightthickness=2, highlightbackground=COLOR_BORDER)
        self.lbl_preview.pack(padx=20, pady=8)

        # Options bar: Switch to clean page & Reset to factory
        opt_bar = tk.Frame(right, bg=COLOR_BG_CARD)
        opt_bar.pack(fill=tk.X, padx=20, pady=(4, 6))

        self.var_switch_clean_page = tk.BooleanVar(value=False)
        cb_clean = tk.Checkbutton(
            opt_bar, text="Nach Upload auf Seite 3 wechseln",
            variable=self.var_switch_clean_page,
            font=("Segoe UI", 9), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD, activeforeground=COLOR_TEXT_MAIN
        )
        cb_clean.pack(side=tk.LEFT)

        btn_reset_theme = tk.Button(
            opt_bar, text="↺ Werkseinstellung Hintergrund & Kacheln", font=("Segoe UI", 8),
            bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MUTED, bd=0, padx=8, pady=3, cursor="hand2",
            command=self._reset_factory_theme
        )
        btn_reset_theme.pack(side=tk.RIGHT)

        # Progress bar & Upload Button
        self.progress_bar = ttk.Progressbar(right, orient=tk.HORIZONTAL, length=480, mode="determinate")
        self.progress_bar.pack(padx=20, pady=(6, 6))

        self.btn_upload = tk.Button(
            right, text="⚡ APPLY THEME TO KB7 DISPLAY", font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT, fg="#000000", activebackground="#00e5ff", activeforeground="#000000",
            bd=0, padx=24, pady=10, cursor="hand2", command=self._upload_selected_theme
        )
        self.btn_upload.pack(padx=20, pady=(6, 12))

        self.lbl_upload_status = tk.Label(right, text="Ready to upload.", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        self.lbl_upload_status.pack(padx=20)

        # SteelSeries Mouse RGB Sync Section
        f_ss = tk.Frame(right, bg="#10151f", bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        f_ss.pack(fill=tk.X, padx=20, pady=(10, 8))

        f_ss_head = tk.Frame(f_ss, bg="#10151f")
        f_ss_head.pack(fill=tk.X, padx=12, pady=(8, 4))

        tk.Label(f_ss_head, text="🖱️ STEELSERIES MOUSE RGB SYNC", font=("Segoe UI", 9, "bold"), fg=COLOR_ACCENT, bg="#10151f").pack(side=tk.LEFT)
        ss_status_txt = "● SteelSeries Aerox 3 verbunden" if (self.steelseries and self.steelseries.connected) else "SteelSeries nicht aktiv"
        ss_status_col = "#00e575" if (self.steelseries and self.steelseries.connected) else COLOR_TEXT_MUTED
        self.lbl_ss_status = tk.Label(f_ss_head, text=ss_status_txt, font=("Segoe UI", 8), fg=ss_status_col, bg="#10151f")
        self.lbl_ss_status.pack(side=tk.RIGHT)

        f_ss_opts = tk.Frame(f_ss, bg="#10151f")
        f_ss_opts.pack(fill=tk.X, padx=12, pady=(0, 6))

        self.var_ss_auto_sync = tk.BooleanVar(value=True)
        cb_ss_auto = tk.Checkbutton(
            f_ss_opts, text="Maus-LEDs automatisch an gewähltes Display-Theme anpassen",
            variable=self.var_ss_auto_sync, font=("Segoe UI", 8), fg=COLOR_TEXT_MAIN, bg="#10151f",
            selectcolor=COLOR_BG_DARK, activebackground="#10151f", activeforeground=COLOR_TEXT_MAIN,
            command=self._on_ss_auto_sync_toggle
        )
        cb_ss_auto.pack(side=tk.LEFT)

        f_ss_colors = tk.Frame(f_ss, bg="#10151f")
        f_ss_colors.pack(fill=tk.X, padx=12, pady=(0, 8))

        quick_colors = [
            ("Matrix Grün", (0, 255, 102), "#00FF66", "#000000"),
            ("Toxic Neon", (57, 255, 20), "#39FF14", "#000000"),
            ("Cyber Cyan", (0, 229, 255), "#00E5FF", "#000000"),
            ("Neon Magenta", (255, 0, 128), "#FF0080", "#FFFFFF"),
            ("Studio Gold", (230, 165, 30), "#E6A51E", "#000000"),
            ("Cyber Purple", (160, 32, 240), "#A020F0", "#FFFFFF"),
            ("Crimson Red", (255, 30, 50), "#FF1E32", "#FFFFFF"),
            ("Pure White", (255, 255, 255), "#FFFFFF", "#000000"),
        ]
        for c_name, rgb, bg_hex, fg_hex in quick_colors:
            btn_c = tk.Button(
                f_ss_colors, text=c_name, font=("Segoe UI", 8, "bold"),
                bg=bg_hex, fg=fg_hex, bd=0, padx=8, pady=3, cursor="hand2",
                command=lambda r=rgb[0], g=rgb[1], b=rgb[2], n=c_name: self._set_mouse_color(r, g, b, n)
            )
            btn_c.pack(side=tk.LEFT, padx=(0, 6))

        # Initial Preview Render
        self._update_preview()

    def _on_ss_auto_sync_toggle(self):
        if self.steelseries and self.var_ss_auto_sync.get():
            self.steelseries.sync_theme(self.theme_var.get())

    def _set_mouse_color(self, r: int, g: int, b: int, name: str):
        if self.steelseries:
            ok = self.steelseries.set_color(r, g, b)
            if ok:
                self.lbl_ss_status.configure(text=f"Maus-Farbe: {name} ({r},{g},{b})", fg=COLOR_ACCENT)

    def _on_theme_selected(self):
        self.custom_image_path = None
        self._update_preview()
        if self.steelseries and getattr(self, "var_ss_auto_sync", None) and self.var_ss_auto_sync.get():
            self.steelseries.sync_theme(self.theme_var.get())

    def _browse_custom_image(self):
        path = filedialog.askopenfilename(
            title="Select 800x480 Background Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if path:
            self.custom_image_path = path
            self.theme_var.set("custom")
            self._update_preview()

    def _update_preview(self):
        try:
            if self.custom_image_path:
                im = Image.open(self.custom_image_path).convert("RGB")
            else:
                preset = self.theme_var.get()
                gen_fn = THEME_PRESETS.get(preset, THEME_PRESETS["tactical_hud"])
                im = gen_fn()

            # Preserve exact aspect ratio of the 480x800 portrait framebuffer inside a 520x312 preview canvas
            canvas = Image.new("RGB", (520, 312), (8, 12, 20))
            im_copy = im.copy()
            im_copy.thumbnail((520, 312), Image.Resampling.LANCZOS)
            ox = (520 - im_copy.width) // 2
            oy = (312 - im_copy.height) // 2
            canvas.paste(im_copy, (ox, oy))
            self.preview_image_tk = ImageTk.PhotoImage(canvas)
            self.lbl_preview.configure(image=self.preview_image_tk)
        except Exception as e:
            print(f"[!] Preview generation error: {e}")

    def _upload_selected_theme(self):
        """Uploads theme in background thread to prevent GUI freezing."""
        def worker():
            self.btn_upload.configure(state=tk.DISABLED)
            self.lbl_upload_status.configure(text="Generating image data...")
            self.progress_bar["value"] = 0

            try:
                if self.custom_image_path:
                    im = Image.open(self.custom_image_path).convert("RGB")
                else:
                    preset = self.theme_var.get()
                    gen_fn = THEME_PRESETS.get(preset, THEME_PRESETS["tactical_hud"])
                    im = gen_fn()

                def progress_cb(msg: str, pct: int):
                    self.root.after(0, lambda: self._update_upload_status(msg, pct))

                # Safe upload avoiding handle conflicts with running daemon
                if self.daemon and self.daemon.device:
                    with self.daemon.lock:
                        self.daemon.device.upload_theme(im, progress_callback=progress_cb)
                        if self.var_switch_clean_page.get():
                            self.daemon.device.set_active_page(3)
                elif self.client and self.hw_connected:
                    progress_cb("Sending upload command to KB7 Daemon (please wait)...", 20)
                    preset_name = None if self.custom_image_path else self.theme_var.get()
                    self.client.apply_theme(name=preset_name, path=self.custom_image_path)
                    if self.var_switch_clean_page.get():
                        self.client.set_page(3)
                    progress_cb("Theme active and visible on KB7 display!", 100)
                else:
                    with KB7Device() as dev:
                        dev.upload_theme(im, progress_callback=progress_cb)
                        if self.var_switch_clean_page.get():
                            dev.set_active_page(3)

                msg = "[+] Theme active on KB7 display!"
                if self.var_switch_clean_page.get():
                    msg += " (Switched to Page 3)"
                    self.page_var.set(3)

                if self.steelseries and self.var_ss_auto_sync.get():
                    self.steelseries.sync_theme(self.theme_var.get())
                self.root.after(0, lambda: self.lbl_upload_status.configure(text=msg, fg=COLOR_ACCENT))
                self.root.after(0, self.refresh_slots_view)
            except Exception as e:
                self.root.after(0, lambda: self.lbl_upload_status.configure(text=f"[!] Upload error: {e}", fg=COLOR_MUTE_ACTIVE))
            finally:
                self.root.after(0, lambda: self.btn_upload.configure(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

    def _update_upload_status(self, msg: str, pct: int):
        self.progress_bar["value"] = pct
        self.lbl_upload_status.configure(text=msg, fg=COLOR_TEXT_MAIN)

    def _reset_factory_theme(self):
        """Resets the keyboard screen to built-in factory wallpaper and 12-tile layout."""
        try:
            if self.daemon and self.daemon.device:
                with self.daemon.lock:
                    self.daemon.device.set_background_mode(0)
                    self.daemon.device.restore_factory_layout()
            elif self.client and self.hw_connected:
                self.client.set_background_mode(0)
                self.client.apply_template(page=1, template_name="factory")
            else:
                with KB7Device() as dev:
                    dev.set_background_mode(0)
                    dev.restore_factory_layout()
            self.refresh_slots_view()
            self.lbl_upload_status.configure(text="[+] Restored factory default wallpaper & 12-tile layout.", fg=COLOR_ACCENT)
        except Exception as e:
            self.lbl_upload_status.configure(text=f"[!] Reset error: {e}", fg=COLOR_MUTE_ACTIVE)

    def _update_progress(self, pct: int, sent: int, total: int):
        self.progress_bar["value"] = pct
        self.lbl_upload_status.configure(text=f"Uploading: {pct}% ({sent // 1024} KB / {total // 1024} KB)")

    def _on_brightness_change(self, val: str):
        v = int(float(val))
        self.lbl_bri_val.configure(text=f"Brightness: {v}%")
        if self.client and self.hw_connected:
            try:
                self.client.set_brightness(v)
            except Exception:
                pass

    def _on_timeout_change(self, val: str):
        v = int(float(val))
        self.lbl_to_val.configure(text=f"Sleep Timeout: {v}s")
        if self.client and self.hw_connected:
            try:
                self.client.set_timeout(v)
            except Exception:
                pass

    def refresh_display_settings(self):
        if self.client and self.hw_connected:
            try:
                s = self.client.get_settings()
                if "brightness" in s:
                    self.slider_brightness.set(s["brightness"])
                    self.lbl_bri_val.configure(text=f"Brightness: {s['brightness']}%")
                if "timeout_seconds" in s:
                    self.slider_timeout.set(s["timeout_seconds"])
                    self.lbl_to_val.configure(text=f"Sleep Timeout: {s['timeout_seconds']}s")
            except Exception:
                pass

    # =========================================================================
    # TAB 2B: SMART STREAM DECK (12x 1x1 COMPACT TILES ON PAGE 3)
    # =========================================================================

    def _build_streamdeck_tab(self, parent: tk.Frame):
        # Top Control & Profile Bar
        top_bar = tk.Frame(parent, bg=COLOR_BG_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        top_bar.pack(fill=tk.X, pady=(2, 4))

        row1 = tk.Frame(top_bar, bg=COLOR_BG_CARD)
        row1.pack(fill=tk.X, padx=14, pady=(8, 3))

        tk.Label(row1, text="DECK-PROFILE (12× 1x1 KLEINE KACHELN):", font=("Segoe UI", 9, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD).pack(side=tk.LEFT, padx=(0, 8))

        deck_profiles = [
            ("stream_media", "🎬 Stream & Companion"),
            ("obs_creator", "🎥 OBS & Creator"),
            ("gaming_discord", "🎮 Gaming & Discord"),
            ("mini_telemetry", "📊 12× Mini-Telemetrie"),
        ]
        for prof_key, prof_lbl in deck_profiles:
            btn_p = tk.Button(
                row1, text=prof_lbl, font=("Segoe UI", 8, "bold"),
                bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=10, pady=4, cursor="hand2",
                command=lambda pk=prof_key: self._load_streamdeck_profile(pk)
            )
            btn_p.pack(side=tk.LEFT, padx=3)

        btn_sync_hw = tk.Button(
            row1, text="⚡ AUF KB7 SEITE 3 FLASHEN & AKTIVIEREN", font=("Segoe UI", 9, "bold"),
            bg="#00e575", fg="#000000", activebackground="#00ff88", bd=0, padx=14, pady=4, cursor="hand2",
            command=self._sync_streamdeck_to_kb7
        )
        btn_sync_hw.pack(side=tk.RIGHT, padx=(6, 0))

        # Row 2: Live Stream Companion & Display-Streaming Bar (Twitch/YouTube/OBS Detector + Auto-Snapshot / Mini-Tile Stream)
        row_stream = tk.Frame(top_bar, bg="#10151f", bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        row_stream.pack(fill=tk.X, padx=14, pady=3)

        tk.Label(row_stream, text="📺 STREAM COMPANION:", font=("Segoe UI", 8, "bold"), fg="#a020f0", bg="#10151f").pack(side=tk.LEFT, padx=(8, 4), pady=5)

        self.lbl_detected_stream = tk.Label(
            row_stream, text="● Suche aktiven Stream (Twitch / YouTube / OBS / Browser)...",
            font=("Segoe UI", 8, "bold"), fg="#00e5ff", bg="#10151f"
        )
        self.lbl_detected_stream.pack(side=tk.LEFT, padx=4)

        btn_focus_strm = tk.Button(
            row_stream, text="🎯 Zum Stream wechseln", font=("Segoe UI", 8, "bold"),
            bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=8, pady=3, cursor="hand2",
            command=self._focus_detected_stream
        )
        btn_focus_strm.pack(side=tk.LEFT, padx=4)

        # Auto-Stream / Diashow Toggle + Mode + Manual Snapshot
        self._auto_stream_running = False
        self.btn_auto_stream = tk.Button(
            row_stream, text="🔄 Auto-Stream / Diashow: AUS", font=("Segoe UI", 8, "bold"),
            bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=10, pady=3, cursor="hand2",
            command=self._toggle_auto_stream_loop
        )
        self.btn_auto_stream.pack(side=tk.RIGHT, padx=6, pady=3)

        self.var_stream_mode = tk.StringVar(value=self.streamdeck.auto_stream_mode)
        cb_strm_mode = ttk.Combobox(
            row_stream,
            values=["mini (142×148 Schnell ~1s)", "full (480×800 Vollbild alle 10s)"],
            state="readonly", width=26
        )
        cb_strm_mode.current(0 if self.streamdeck.auto_stream_mode == "mini" else 1)
        cb_strm_mode.pack(side=tk.RIGHT, padx=4)
        cb_strm_mode.bind(
            "<<ComboboxSelected>>",
            lambda e: setattr(self.streamdeck, "auto_stream_mode", "mini" if cb_strm_mode.get().startswith("mini") else "full")
        )

        btn_mini_snap = tk.Button(
            row_stream, text="🎞️ Mini-Frame (142×148)", font=("Segoe UI", 8, "bold"),
            bg="#a020f0", fg="#ffffff", bd=0, padx=8, pady=3, cursor="hand2",
            command=self._push_mini_stream_frame_to_kb7
        )
        btn_mini_snap.pack(side=tk.RIGHT, padx=3)

        btn_snap = tk.Button(
            row_stream, text="📸 Vollbild-Snapshot -> KB7", font=("Segoe UI", 8, "bold"),
            bg=COLOR_ACCENT, fg="#000000", bd=0, padx=8, pady=3, cursor="hand2",
            command=self._push_live_snapshot_to_kb7
        )
        btn_snap.pack(side=tk.RIGHT, padx=3)

        # Row 3: Tile Size Controls (UI & Hardware) + Touch Bridge Toggle
        row2 = tk.Frame(top_bar, bg=COLOR_BG_CARD)
        row2.pack(fill=tk.X, padx=14, pady=(2, 6))

        tk.Label(row2, text="UI-KACHELGRÖẞE:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(side=tk.LEFT, padx=(0, 6))

        self.var_sd_ui_size = tk.StringVar(value=self.streamdeck.ui_tile_size)
        for sz_val, sz_lbl in [("small", "Klein (Kompakt)"), ("medium", "Mittel"), ("large", "Groß")]:
            rb = tk.Radiobutton(
                row2, text=sz_lbl, variable=self.var_sd_ui_size, value=sz_val,
                font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
                selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
                command=self._on_sd_tile_size_changed
            )
            rb.pack(side=tk.LEFT, padx=3)

        tk.Label(row2, text="  |  KB7 DISPLAY-KACHELGRÖẞE:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(side=tk.LEFT, padx=(8, 4))

        self.var_sd_hw_small = tk.BooleanVar(value=self.streamdeck.hw_small_tiles)
        cb_hw_sz = tk.Checkbutton(
            row2, text="1x1 Kleine Kacheln erzwingen (alle 12 Slots im 4×3 Raster)",
            variable=self.var_sd_hw_small, font=("Segoe UI", 8, "bold"), fg="#00e575", bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
            command=self._on_sd_tile_size_changed
        )
        cb_hw_sz.pack(side=tk.LEFT, padx=4)

        self.var_sd_touch_bridge = tk.BooleanVar(value=True)
        cb_touch = tk.Checkbutton(
            row2, text="Touchscreen-Aktionen aktiv",
            variable=self.var_sd_touch_bridge, font=("Segoe UI", 8), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD
        )
        cb_touch.pack(side=tk.RIGHT, padx=4)

        # Main Split Area: Left = 4x3 Compact Stream Deck Grid, Right = Smart Tile Inspector
        body = tk.Frame(parent, bg=COLOR_BG_DARK)
        body.pack(fill=tk.BOTH, expand=True)

        # Left Grid Container
        self.sd_grid_card = tk.Frame(body, bg=COLOR_BG_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.sd_grid_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=2)

        grid_head = tk.Frame(self.sd_grid_card, bg=COLOR_BG_CARD)
        grid_head.pack(fill=tk.X, padx=14, pady=(10, 4))

        tk.Label(
            grid_head, text="🎛️ INTERAKTIVES 4×3 STREAM DECK RASTER (KLICK = AUSFÜHREN & AUSWÄHLEN)",
            font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD
        ).pack(side=tk.LEFT)

        self.lbl_sd_status = tk.Label(
            grid_head, text="Bereit (Seite 3 • 12× 1x1 Kleine Kacheln)",
            font=("Segoe UI", 8, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD
        )
        self.lbl_sd_status.pack(side=tk.RIGHT)

        self.sd_grid_frame = tk.Frame(self.sd_grid_card, bg=COLOR_BG_CARD)
        self.sd_grid_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Right Inspector Card
        insp = tk.Frame(body, bg=COLOR_BG_CARD, width=290, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        insp.pack(side=tk.RIGHT, fill=tk.Y, pady=2)
        insp.pack_propagate(False)

        tk.Label(insp, text="⚙ KACHEL ANPASSEN", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD).pack(anchor="w", padx=14, pady=(12, 4))

        self.lbl_sd_edit_slot = tk.Label(insp, text="Ausgewählt: Slot 0 (Oben Links)", font=("Segoe UI", 9, "bold"), fg="#00e575", bg=COLOR_BG_CARD)
        self.lbl_sd_edit_slot.pack(anchor="w", padx=14, pady=(0, 8))

        # Icon + Title
        f_it = tk.Frame(insp, bg=COLOR_BG_CARD)
        f_it.pack(fill=tk.X, padx=14, pady=3)
        tk.Label(f_it, text="Icon & Titel:", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(anchor="w")

        row_it = tk.Frame(f_it, bg=COLOR_BG_CARD)
        row_it.pack(fill=tk.X, pady=2)
        self.ent_sd_icon = tk.Entry(row_it, width=4, font=("Segoe UI", 10), bg=COLOR_BG_DARK, fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, bd=1)
        self.ent_sd_icon.pack(side=tk.LEFT, padx=(0, 6))
        self.ent_sd_title = tk.Entry(row_it, font=("Segoe UI", 9, "bold"), bg=COLOR_BG_DARK, fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, bd=1)
        self.ent_sd_title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Subtitle
        f_sub = tk.Frame(insp, bg=COLOR_BG_CARD)
        f_sub.pack(fill=tk.X, padx=14, pady=3)
        tk.Label(f_sub, text="Untertitel (Info):", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(anchor="w")
        self.ent_sd_subtitle = tk.Entry(f_sub, font=("Segoe UI", 9), bg=COLOR_BG_DARK, fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, bd=1)
        self.ent_sd_subtitle.pack(fill=tk.X, pady=2)

        # KB7 Hardware Label (max 11 chars for Report 0x29)
        f_hwlbl = tk.Frame(insp, bg=COLOR_BG_CARD)
        f_hwlbl.pack(fill=tk.X, padx=14, pady=3)
        tk.Label(f_hwlbl, text="KB7 Display-Text (max. 11 Zeichen):", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(anchor="w")
        self.ent_sd_hw_label = tk.Entry(f_hwlbl, font=("Consolas", 9, "bold"), bg=COLOR_BG_DARK, fg="#00e575", insertbackground=COLOR_TEXT_MAIN, bd=1)
        self.ent_sd_hw_label.pack(fill=tk.X, pady=2)

        # Smart Action Dropdown
        f_act = tk.Frame(insp, bg=COLOR_BG_CARD)
        f_act.pack(fill=tk.X, padx=14, pady=3)
        tk.Label(f_act, text="Smart-Aktion (PC / Stream / Hotkey):", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(anchor="w")

        self._sd_action_labels: List[str] = []
        self._sd_label_to_action: Dict[str, str] = {}
        self._sd_action_to_label: Dict[str, str] = {}
        for act_id, meta in STREAMDECK_ACTIONS.items():
            lbl = meta["name"]
            self._sd_action_labels.append(lbl)
            self._sd_label_to_action[lbl] = act_id
            self._sd_action_to_label[act_id] = lbl

        self.cb_sd_action = ttk.Combobox(f_act, values=self._sd_action_labels, state="readonly")
        self.cb_sd_action.pack(fill=tk.X, pady=2)

        # KB7 Hardware 1x1 Tile Type Dropdown
        f_hw = tk.Frame(insp, bg=COLOR_BG_CARD)
        f_hw.pack(fill=tk.X, padx=14, pady=3)
        tk.Label(f_hw, text="KB7 Hardware-Kachel (1x1 Klein):", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(anchor="w")

        self._sd_hw_choices: List[str] = []
        self._sd_hw_map: Dict[str, int] = {}
        for app_id, w in sorted(WIDGET_CATALOG.items(), key=lambda x: (x[1].span != (1, 1), x[1].category, x[1].name)):
            span_tag = "1x1 Klein" if w.span == (1, 1) else f"{w.span[0]}x{w.span[1]} Groß"
            lbl = f"[{span_tag}] {w.name} (#{app_id})"
            self._sd_hw_choices.append(lbl)
            self._sd_hw_map[lbl] = app_id

        self.cb_sd_hw_widget = ttk.Combobox(f_hw, values=self._sd_hw_choices, state="readonly")
        self.cb_sd_hw_widget.pack(fill=tk.X, pady=2)

        # Save & Test Buttons
        btn_save_tile = tk.Button(
            insp, text="💾 Kachel speichern & auf KB7 senden", font=("Segoe UI", 9, "bold"),
            bg=COLOR_ACCENT, fg="#000000", bd=0, padx=12, pady=7, cursor="hand2",
            command=self._save_streamdeck_tile
        )
        btn_save_tile.pack(fill=tk.X, padx=14, pady=(12, 4))

        btn_test_tile = tk.Button(
            insp, text="▶ Aktion jetzt testen", font=("Segoe UI", 8, "bold"),
            bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=12, pady=5, cursor="hand2",
            command=lambda: self._trigger_streamdeck_slot(self.selected_sd_slot, from_hw=False)
        )
        btn_test_tile.pack(fill=tk.X, padx=14, pady=2)

        self._render_streamdeck_grid()
        self._select_streamdeck_slot(0)

    def _on_sd_tile_size_changed(self):
        self.streamdeck.ui_tile_size = self.var_sd_ui_size.get()
        self.streamdeck.hw_small_tiles = bool(self.var_sd_hw_small.get())
        self.streamdeck.save_config()
        self._render_streamdeck_grid()

    def _render_streamdeck_grid(self):
        for child in self.sd_grid_frame.winfo_children():
            child.destroy()

        sz = self.streamdeck.ui_tile_size
        if sz == "small":
            pad_x, pad_y = 4, 4
            icon_font = ("Segoe UI Emoji", 13, "bold")
            title_font = ("Segoe UI", 8, "bold")
            sub_font = ("Segoe UI", 7)
            badge_font = ("Consolas", 7)
        elif sz == "medium":
            pad_x, pad_y = 6, 6
            icon_font = ("Segoe UI Emoji", 16, "bold")
            title_font = ("Segoe UI", 9, "bold")
            sub_font = ("Segoe UI", 8)
            badge_font = ("Consolas", 7)
        else:
            pad_x, pad_y = 8, 8
            icon_font = ("Segoe UI Emoji", 20, "bold")
            title_font = ("Segoe UI", 10, "bold")
            sub_font = ("Segoe UI", 8)
            badge_font = ("Consolas", 8)

        for r in range(3):
            self.sd_grid_frame.rowconfigure(r, weight=1, uniform="sd_row")
        for c in range(4):
            self.sd_grid_frame.columnconfigure(c, weight=1, uniform="sd_col")

        for idx, tile in enumerate(self.streamdeck.tiles[:12]):
            r, c = divmod(idx, 4)
            is_sel = (idx == self.selected_sd_slot)
            border_col = tile.color if is_sel else COLOR_BORDER
            border_w = 2 if is_sel else 1
            bg_col = "#1a2230" if is_sel else "#111620"

            cell = tk.Frame(
                self.sd_grid_frame, bg=bg_col, bd=0,
                highlightthickness=border_w, highlightbackground=border_col, cursor="hand2"
            )
            cell.grid(row=r, column=c, sticky="nsew", padx=pad_x, pady=pad_y)

            # Top row inside tile: Slot # + 1x1 HW label badge
            top_line = tk.Frame(cell, bg=bg_col)
            top_line.pack(fill=tk.X, padx=6, pady=(4, 0))

            lbl_s = tk.Label(top_line, text=f"S{idx}", font=badge_font, fg=COLOR_TEXT_MUTED, bg=bg_col)
            lbl_s.pack(side=tk.LEFT)

            hw_tag = "1x1" if self.streamdeck.hw_small_tiles else "2x1"
            lbl_hw = tk.Label(top_line, text=f"[{hw_tag}: {tile.hw_label or tile.hw_app_id}]", font=badge_font, fg=tile.color, bg=bg_col)
            lbl_hw.pack(side=tk.RIGHT)

            # Center Icon & Title
            lbl_ico = tk.Label(cell, text=tile.icon, font=icon_font, fg=tile.color, bg=bg_col, cursor="hand2")
            lbl_ico.pack(pady=(1, 0))

            lbl_t = tk.Label(cell, text=tile.title, font=title_font, fg=COLOR_TEXT_MAIN, bg=bg_col, cursor="hand2")
            lbl_t.pack()

            lbl_sub = tk.Label(cell, text=tile.subtitle, font=sub_font, fg=COLOR_TEXT_MUTED, bg=bg_col, cursor="hand2")
            lbl_sub.pack(pady=(0, 3))

            for w in (cell, top_line, lbl_s, lbl_hw, lbl_ico, lbl_t, lbl_sub):
                w.bind("<Button-1>", lambda e, s=idx: self._on_sd_tile_clicked(s))

    def _on_sd_tile_clicked(self, slot_index: int):
        self._select_streamdeck_slot(slot_index)
        self._trigger_streamdeck_slot(slot_index, from_hw=False)

    def _select_streamdeck_slot(self, slot_index: int):
        self.selected_sd_slot = slot_index
        tile = self.streamdeck.tiles[slot_index]
        self.lbl_sd_edit_slot.configure(text=f"Ausgewählt: Slot {slot_index} (Zeile {slot_index // 4 + 1}, Spalte {slot_index % 4 + 1})")

        self.ent_sd_icon.delete(0, tk.END)
        self.ent_sd_icon.insert(0, tile.icon)

        self.ent_sd_title.delete(0, tk.END)
        self.ent_sd_title.insert(0, tile.title)

        self.ent_sd_subtitle.delete(0, tk.END)
        self.ent_sd_subtitle.insert(0, tile.subtitle)

        self.ent_sd_hw_label.delete(0, tk.END)
        self.ent_sd_hw_label.insert(0, tile.hw_label)

        act_lbl = self._sd_action_to_label.get(tile.action_id, self._sd_action_labels[0])
        self.cb_sd_action.set(act_lbl)

        # Match hardware widget
        matched_hw = self._sd_hw_choices[0]
        for ch, aid in self._sd_hw_map.items():
            if aid == tile.hw_app_id:
                matched_hw = ch
                break
        self.cb_sd_hw_widget.set(matched_hw)
        self._render_streamdeck_grid()

    def _trigger_streamdeck_slot(self, slot_index: int, from_hw: bool = False):
        msg = self.streamdeck.execute_tile_action(
            slot_index,
            mixer=self.mixer,
            steelseries=self.steelseries,
            snapshot_callback=self._push_live_snapshot_to_kb7,
            toggle_auto_stream_callback=self._toggle_auto_stream_loop,
        )
        prefix = "[KB7 Touch]" if from_hw else "[Stream Deck]"
        self.lbl_sd_status.configure(text=f"{prefix} {msg}", fg="#00e575")

    def _focus_detected_stream(self):
        wins = scan_stream_windows()
        if wins:
            focus_window_by_hwnd(wins[0].hwnd)
            self.lbl_sd_status.configure(
                text=f"🎯 Fokus gewechselt zu: [{wins[0].platform}] {wins[0].clean_title}",
                fg="#00e575"
            )
        else:
            self.lbl_sd_status.configure(
                text="ℹ Kein aktives Twitch / YouTube / OBS / Browser-Fenster gefunden.",
                fg=COLOR_ACCENT_ALT
            )

    def _push_mini_stream_frame_to_kb7(self):
        """Streams a fast 142x148 Mini-Tile frame (Slot 0x40, ~0.9s) to the KB7 display."""
        def worker():
            self.root.after(0, lambda: self.lbl_sd_status.configure(text="🎞️ Sende schnelles 142×148 Mini-Frame (Slot 0x40)...", fg="#a020f0"))
            try:
                snap_im = capture_screen_snapshot_for_kb7("MINI STREAM")
                if self.daemon and self.daemon.device:
                    with self.daemon.lock:
                        self.daemon.device.upload_mini_stream_frame(snap_im)
                else:
                    with KB7Device() as dev:
                        dev.upload_mini_stream_frame(snap_im)
                self.root.after(0, lambda: self.lbl_sd_status.configure(
                    text="✓ Schnelles 142×148 Mini-Stream-Frame auf KB7 (Slot 0x40) aktualisiert!", fg="#00e575"
                ))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_sd_status.configure(text=f"[!] Mini-Stream Fehler: {e}", fg=COLOR_MUTE_ACTIVE))

        threading.Thread(target=worker, daemon=True).start()

    def _toggle_auto_stream_loop(self):
        """Toggles the automatic Snapshot / Mini-Tile Slideshow Stream to the KB7 display."""
        self._auto_stream_running = not getattr(self, "_auto_stream_running", False)
        if self._auto_stream_running:
            self.btn_auto_stream.configure(text="🔄 Auto-Stream / Diashow: AKTIV ●", bg="#00e575", fg="#000000")
            self.lbl_sd_status.configure(text="🔄 Auto-Stream aufs KB7 Display gestartet!", fg="#00e575")
            threading.Thread(target=self._run_auto_stream_worker, daemon=True).start()
        else:
            self.btn_auto_stream.configure(text="🔄 Auto-Stream / Diashow: AUS", bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN)
            self.lbl_sd_status.configure(text="⏹ Auto-Stream gestoppt.", fg=COLOR_TEXT_MUTED)

    def _run_auto_stream_worker(self):
        while self.running and getattr(self, "_auto_stream_running", False):
            try:
                snap_im = capture_screen_snapshot_for_kb7("AUTO STREAM")
                if self.streamdeck.auto_stream_mode == "mini":
                    if self.daemon and self.daemon.device:
                        with self.daemon.lock:
                            self.daemon.device.upload_mini_stream_frame(snap_im)
                    else:
                        with KB7Device() as dev:
                            dev.upload_mini_stream_frame(snap_im)
                    self.root.after(0, lambda: self.lbl_sd_status.configure(
                        text=f"🎞️ Auto-Mini-Stream (142×148) Frame übertragen ({time.strftime('%H:%M:%S')})", fg="#00e575"
                    ))
                    time.sleep(1.5)
                else:
                    if self.daemon and self.daemon.device:
                        with self.daemon.lock:
                            self.daemon.device.upload_theme(snap_im)
                            self.daemon.device.set_active_page(3)
                    else:
                        with KB7Device() as dev:
                            dev.upload_theme(snap_im)
                            dev.set_active_page(3)
                    self.root.after(0, lambda: self.lbl_sd_status.configure(
                        text=f"📸 Auto-Vollbild-Snapshot übertragen ({time.strftime('%H:%M:%S')})", fg="#00e575"
                    ))
                    time.sleep(max(5, self.streamdeck.auto_stream_interval))
            except Exception as e:
                print(f"[!] Auto-stream loop warning: {e}")
                time.sleep(3.0)

    def _save_streamdeck_tile(self):
        idx = self.selected_sd_slot
        tile = self.streamdeck.tiles[idx]
        tile.icon = self.ent_sd_icon.get().strip() or "⚡"
        tile.title = self.ent_sd_title.get().strip() or f"SLOT {idx}"
        tile.subtitle = self.ent_sd_subtitle.get().strip()
        tile.hw_label = self.ent_sd_hw_label.get().strip()[:11]
        tile.action_id = self._sd_label_to_action.get(self.cb_sd_action.get(), "none")
        tile.hw_app_id = self._sd_hw_map.get(self.cb_sd_hw_widget.get(), 12)

        self.streamdeck.save_config()
        self._render_streamdeck_grid()
        self._sync_streamdeck_to_kb7()

    def _load_streamdeck_profile(self, profile_name: str):
        self.streamdeck.load_profile(profile_name)
        self._select_streamdeck_slot(0)
        self._sync_streamdeck_to_kb7()

    def _sync_streamdeck_to_kb7(self):
        """Flashes the 12 compact 1x1 Stream Deck tiles + custom labels to Page 3 of the KB7."""
        def worker():
            self.root.after(0, lambda: self.lbl_sd_status.configure(text="Übertrage 12× 1x1 Stream Deck Kacheln auf KB7 Seite 3...", fg=COLOR_ACCENT))
            try:
                slots_cfg = self.streamdeck.to_hw_slots_config()
                small = self.streamdeck.hw_small_tiles
                if self.daemon and self.daemon.device:
                    with self.daemon.lock:
                        self.daemon.device.apply_streamdeck_page(slots_cfg, page_index=2, small_tiles=small)
                elif self.client and self.hw_connected:
                    self.client.apply_streamdeck(slots_cfg, page=3, small_tiles=small)
                else:
                    with KB7Device() as dev:
                        dev.apply_streamdeck_page(slots_cfg, page_index=2, small_tiles=small)

                self.page_var.set(3)
                self.root.after(0, self.refresh_slots_view)
                self.root.after(0, lambda: self.lbl_sd_status.configure(
                    text="✓ Stream Deck (12× 1x1 kleine Kacheln) aktiv auf KB7 Seite 3!", fg="#00e575"
                ))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_sd_status.configure(text=f"[!] Sync-Fehler: {e}", fg=COLOR_MUTE_ACTIVE))

        threading.Thread(target=worker, daemon=True).start()

    def _push_live_snapshot_to_kb7(self):
        """Captures a live screen/stream snapshot and uploads it to the KB7 display."""
        def worker():
            self.root.after(0, lambda: self.lbl_sd_status.configure(text="📸 Erfasse Live-Snapshot für KB7 (480×800)...", fg=COLOR_ACCENT))
            try:
                snap_im = capture_screen_snapshot_for_kb7("LIVE STREAM SNAPSHOT")

                def prog_cb(msg: str, pct: int):
                    self.root.after(0, lambda: self.lbl_sd_status.configure(text=f"📸 Snapshot Upload: {pct}%", fg=COLOR_ACCENT))

                if self.daemon and self.daemon.device:
                    with self.daemon.lock:
                        self.daemon.device.upload_theme(snap_im, progress_callback=prog_cb)
                elif self.client and self.hw_connected:
                    with KB7Device() as dev:
                        dev.upload_theme(snap_im, progress_callback=prog_cb)
                else:
                    with KB7Device() as dev:
                        dev.upload_theme(snap_im, progress_callback=prog_cb)

                self.root.after(0, lambda: self.lbl_sd_status.configure(text="✓ Live-Snapshot auf KB7 Display aktiv!", fg="#00e575"))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_sd_status.configure(text=f"[!] Snapshot-Fehler: {e}", fg=COLOR_MUTE_ACTIVE))

        threading.Thread(target=worker, daemon=True).start()

    # =========================================================================
    # TAB 2C: LEUCHTEFFEKTE & RGB CUSTOMIZER (7-ZONEN KB7 + STEELSERIES MAUS)
    # =========================================================================

    def _send_kb7_lighting_hw(
        self,
        mode: int = 7,
        speed: int = 6,
        brightness: int = 100,
        color_flag: int = 0x0B,
        direction: int = 1,
        group_colors: Optional[List[Tuple[int, int, int]]] = None,
        key_offsets_rgb: Optional[Dict[int, Tuple[int, int, int]]] = None,
    ) -> bool:
        """Dispatches Report 0x11 (348B) keyboard RGB configuration safely via Daemon, Client, or direct HID."""
        try:
            if self.daemon and self.daemon.device:
                with self.daemon.lock:
                    return self.daemon.device.set_keyboard_lighting(
                        mode=mode,
                        speed=speed,
                        brightness=brightness,
                        color_flag=color_flag,
                        direction=direction,
                        group_colors=group_colors,
                        key_offsets_rgb=key_offsets_rgb,
                    )
            elif self.client and self.hw_connected:
                return self.client.set_keyboard_lighting(
                    mode=mode,
                    speed=speed,
                    brightness=brightness,
                    color_flag=color_flag,
                    direction=direction,
                    group_colors=group_colors,
                    key_offsets_rgb=key_offsets_rgb,
                )
            else:
                with KB7Device() as dev:
                    return dev.set_keyboard_lighting(
                        mode=mode,
                        speed=speed,
                        brightness=brightness,
                        color_flag=color_flag,
                        direction=direction,
                        group_colors=group_colors,
                        key_offsets_rgb=key_offsets_rgb,
                    )
        except Exception as e:
            print(f"[!] Hardware lighting dispatch warning: {e}")
            return False

    def _build_lighting_tab(self, parent: tk.Frame):
        content = tk.Frame(parent, bg=COLOR_BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, pady=2)

        # Left Panel: Effect Catalog & Speed/Brightness/Sync Controls
        left = tk.Frame(content, bg=COLOR_BG_CARD, width=370, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8), pady=2)
        left.pack_propagate(False)

        tk.Label(
            left, text="💡 LEUCHTEFFEKTE AUSWÄHLEN",
            font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD
        ).pack(anchor="w", padx=14, pady=(10, 4))

        # Scrollable or Listbox/Radiobutton area for the 16 effects
        fx_list_frame = tk.Frame(left, bg="#0d1117", bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        fx_list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        self.lb_effects = tk.Listbox(
            fx_list_frame, bg="#0d1117", fg=COLOR_TEXT_MAIN,
            selectbackground=COLOR_ACCENT, selectforeground="#000000",
            font=("Segoe UI", 9, "bold"), bd=0, highlightthickness=0, activestyle="none", height=12
        )
        sb_fx = ttk.Scrollbar(fx_list_frame, orient=tk.VERTICAL, command=self.lb_effects.yview)
        self.lb_effects.configure(yscrollcommand=sb_fx.set)
        self.lb_effects.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        sb_fx.pack(side=tk.RIGHT, fill=tk.Y)

        self._effect_keys: List[str] = list(LIGHTING_EFFECTS.keys())
        sel_idx = 0
        for i, eff_id in enumerate(self._effect_keys):
            meta = LIGHTING_EFFECTS[eff_id]
            self.lb_effects.insert(tk.END, str(meta["name"]))
            if eff_id == self.lighting.effect_id:
                sel_idx = i

        self.lb_effects.selection_set(sel_idx)
        self.lb_effects.see(sel_idx)
        self.lb_effects.bind("<<ListboxSelect>>", self._on_lighting_effect_selected)

        self.lbl_fx_desc = tk.Label(
            left, text=str(LIGHTING_EFFECTS[self.lighting.effect_id]["desc"]),
            font=("Segoe UI", 8), fg="#00e575", bg=COLOR_BG_CARD, wraplength=340, justify=tk.LEFT
        )
        self.lbl_fx_desc.pack(anchor="w", padx=14, pady=(2, 6))

        # Sliders: Speed (1..11) & Brightness (0..100%)
        f_sliders = tk.Frame(left, bg=COLOR_BG_CARD)
        f_sliders.pack(fill=tk.X, padx=14, pady=2)

        row_spd = tk.Frame(f_sliders, bg=COLOR_BG_CARD)
        row_spd.pack(fill=tk.X, pady=2)
        self.lbl_fx_speed = tk.Label(row_spd, text=f"Geschwindigkeit: {self.lighting.speed} / 11", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        self.lbl_fx_speed.pack(side=tk.LEFT)
        self.lbl_fx_dir = tk.Label(row_spd, text="Richtung:", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        self.lbl_fx_dir.pack(side=tk.RIGHT, padx=(4, 0))

        self.slider_fx_speed = ttk.Scale(f_sliders, from_=1, to=11, orient=tk.HORIZONTAL, command=self._on_fx_speed_changed)
        self.slider_fx_speed.set(self.lighting.speed)
        self.slider_fx_speed.pack(fill=tk.X, pady=(0, 4))

        row_bri = tk.Frame(f_sliders, bg=COLOR_BG_CARD)
        row_bri.pack(fill=tk.X, pady=2)
        self.lbl_fx_bri = tk.Label(row_bri, text=f"LED-Helligkeit: {self.lighting.brightness}%", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        self.lbl_fx_bri.pack(side=tk.LEFT)

        self.slider_fx_bri = ttk.Scale(f_sliders, from_=0, to=100, orient=tk.HORIZONTAL, command=self._on_fx_bri_changed)
        self.slider_fx_bri.set(self.lighting.brightness)
        self.slider_fx_bri.pack(fill=tk.X, pady=(0, 4))

        # Direction & Sync Toggles
        f_toggles = tk.Frame(left, bg=COLOR_BG_CARD)
        f_toggles.pack(fill=tk.X, padx=14, pady=(2, 8))

        self.var_fx_kb_en = tk.BooleanVar(value=self.lighting.kb_enabled)
        cb_kb = tk.Checkbutton(
            f_toggles, text="⌨️ KB7 Tastatur-RGB aktiv", variable=self.var_fx_kb_en,
            font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
            command=self._on_fx_toggles_changed
        )
        cb_kb.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.var_fx_mouse_en = tk.BooleanVar(value=self.lighting.mouse_sync_enabled)
        cb_ms = tk.Checkbutton(
            f_toggles, text="🖱️ SteelSeries Maus-Sync", variable=self.var_fx_mouse_en,
            font=("Segoe UI", 8, "bold"), fg="#00e575", bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
            command=self._on_fx_toggles_changed
        )
        cb_ms.grid(row=0, column=1, sticky="w")

        self.var_fx_rainbow = tk.BooleanVar(value=self.lighting.rainbow_override)
        cb_rb = tk.Checkbutton(
            f_toggles, text="🌈 Hardware-Regenbogen (statt Custom-Farben)", variable=self.var_fx_rainbow,
            font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
            command=self._on_fx_toggles_changed
        )
        cb_rb.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        # Right Panel: 3 Customizable Color Channels + Quick Palettes + Live 7-Zone Keyboard & Mouse Preview
        right = tk.Frame(content, bg=COLOR_BG_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=2)

        tk.Label(
            right, text="🎨 INDIVIDUELLE FARBANPASSUNG (3 FARBKANÄLE FÜR VERLÄUFE, WELLEN & ZONEN)",
            font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD
        ).pack(anchor="w", padx=16, pady=(10, 6))

        # 3 Color Channel Cards side by side
        colors_row = tk.Frame(right, bg=COLOR_BG_CARD)
        colors_row.pack(fill=tk.X, padx=16, pady=4)
        for c_idx in range(3):
            colors_row.columnconfigure(c_idx, weight=1, uniform="col_chan")

        channel_meta = [
            (1, "FARBE 1 (PRIMÄR)", "Haupttasten / Verlauf Start / Ruhe", self.lighting.color1_hex),
            (2, "FARBE 2 (SEKUNDÄR)", "WASD & F-Tasten / Verlauf Mitte", self.lighting.color2_hex),
            (3, "FARBE 3 (AKZENT)", "Pfeiltasten & Underglow / Peak", self.lighting.color3_hex),
        ]
        self._color_swatches: Dict[int, tk.Button] = {}
        self._color_entries: Dict[int, tk.Entry] = {}

        for idx, title, sub, init_hex in channel_meta:
            c_card = tk.Frame(colors_row, bg="#10151f", bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
            c_card.grid(row=0, column=idx - 1, sticky="nsew", padx=4, pady=2)

            tk.Label(c_card, text=title, font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MAIN, bg="#10151f").pack(anchor="w", padx=10, pady=(8, 0))
            tk.Label(c_card, text=sub, font=("Segoe UI", 7), fg=COLOR_TEXT_MUTED, bg="#10151f").pack(anchor="w", padx=10, pady=(0, 6))

            swatch_btn = tk.Button(
                c_card, text="🎨 Farbe wählen...", font=("Segoe UI", 9, "bold"),
                bg=init_hex, fg=self._ideal_text_fg(init_hex), bd=0, pady=8, cursor="hand2",
                command=lambda ch=idx: self._pick_custom_color(ch)
            )
            swatch_btn.pack(fill=tk.X, padx=10, pady=4)
            self._color_swatches[idx] = swatch_btn

            hex_row = tk.Frame(c_card, bg="#10151f")
            hex_row.pack(fill=tk.X, padx=10, pady=(2, 8))
            tk.Label(hex_row, text="HEX:", font=("Consolas", 8, "bold"), fg=COLOR_TEXT_MUTED, bg="#10151f").pack(side=tk.LEFT)

            ent_hex = tk.Entry(hex_row, width=9, font=("Consolas", 9, "bold"), bg=COLOR_BG_DARK, fg=COLOR_TEXT_MAIN, insertbackground=COLOR_TEXT_MAIN, bd=1)
            ent_hex.insert(0, init_hex)
            ent_hex.pack(side=tk.LEFT, padx=6)
            ent_hex.bind("<Return>", lambda e, ch=idx: self._apply_hex_entry(ch))
            self._color_entries[idx] = ent_hex

            btn_ok = tk.Button(
                hex_row, text="OK", font=("Segoe UI", 7, "bold"),
                bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=6, pady=2, cursor="hand2",
                command=lambda ch=idx: self._apply_hex_entry(ch)
            )
            btn_ok.pack(side=tk.RIGHT)

        # Quick 3-Color Palette Presets
        tk.Label(
            right, text="⚡ 1-KLICK FARBPALETTEN (SETZT FARBE 1 + FARBE 2 + FARBE 3):",
            font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD
        ).pack(anchor="w", padx=16, pady=(8, 4))

        pal_grid = tk.Frame(right, bg=COLOR_BG_CARD)
        pal_grid.pack(fill=tk.X, padx=16, pady=2)
        for col_i in range(4):
            pal_grid.columnconfigure(col_i, weight=1, uniform="pal_col")

        for p_idx, (p_name, h1, h2, h3) in enumerate(COLOR_PALETTES):
            r, c = divmod(p_idx, 4)
            p_btn = tk.Button(
                pal_grid, text=p_name, font=("Segoe UI", 8, "bold"),
                bg=h1, fg=self._ideal_text_fg(h1), bd=0, padx=6, pady=5, cursor="hand2",
                command=lambda c1=h1, c2=h2, c3=h3, pn=p_name: self._apply_color_palette(c1, c2, c3, pn)
            )
            p_btn.grid(row=r, column=c, sticky="ew", padx=3, pady=3)

        # Live 7-Zone Keyboard + WASD/Arrows + SteelSeries Mouse Visualizer Canvas
        tk.Label(
            right, text="🎹 LIVE RGB-ZONEN VORSCHAU (KB7 7-GRUPPEN PLANAR-RGB + WASD/PFEILE + MAUS):",
            font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD
        ).pack(anchor="w", padx=16, pady=(10, 4))

        self.canvas_rgb_preview = tk.Canvas(
            right, bg="#080c14", height=150, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER
        )
        self.canvas_rgb_preview.pack(fill=tk.X, padx=16, pady=4)

        # Bottom Action & Status Bar
        bot_bar = tk.Frame(right, bg=COLOR_BG_CARD)
        bot_bar.pack(fill=tk.X, padx=16, pady=(6, 10))

        self.btn_apply_lighting = tk.Button(
            bot_bar, text="⚡ LEUCHTEFFEKT & FARBEN JETZT AUF HARDWARE ANWENDEN",
            font=("Segoe UI", 9, "bold"), bg="#00e575", fg="#000000", activebackground="#00ff88",
            bd=0, padx=16, pady=7, cursor="hand2", command=self._on_apply_lighting_clicked
        )
        self.btn_apply_lighting.pack(side=tk.LEFT)

        self.lbl_lighting_status = tk.Label(
            bot_bar, text="✓ Echtzeit-Synchronisation aktiv",
            font=("Segoe UI", 8, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD
        )
        self.lbl_lighting_status.pack(side=tk.RIGHT, padx=8)

        # Hook live preview callback
        self.lighting.set_preview_callback(self._schedule_rgb_preview_update)
        self._draw_rgb_preview(self.lighting.current_groups, self.lighting.current_key_offsets, self.lighting.current_mouse_rgb)

    @staticmethod
    def _ideal_text_fg(hex_col: str) -> str:
        r, g, b = hex_to_rgb(hex_col)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "#000000" if lum > 135 else "#FFFFFF"

    def _on_lighting_effect_selected(self, event=None):
        sel = self.lb_effects.curselection()
        if not sel:
            return
        eff_id = self._effect_keys[sel[0]]
        self.lighting.effect_id = eff_id
        meta = LIGHTING_EFFECTS[eff_id]
        self.lbl_fx_desc.configure(text=str(meta["desc"]))
        self.lighting.save_config()
        self.lighting.apply_now()
        self.lbl_lighting_status.configure(text=f"✓ Aktiv: {meta['name']}", fg="#00e575")

    def _on_fx_speed_changed(self, val: str):
        v = max(1, min(11, int(round(float(val)))))
        self.lighting.speed = v
        if hasattr(self, "lbl_fx_speed"):
            self.lbl_fx_speed.configure(text=f"Geschwindigkeit: {v} / 11")
        self.lighting.save_config()
        if not LIGHTING_EFFECTS.get(self.lighting.effect_id, {}).get("dynamic", False):
            self.lighting.apply_now()

    def _on_fx_bri_changed(self, val: str):
        v = max(0, min(100, int(round(float(val)))))
        self.lighting.brightness = v
        if hasattr(self, "lbl_fx_bri"):
            self.lbl_fx_bri.configure(text=f"LED-Helligkeit: {v}%")
        self.lighting.save_config()
        if not LIGHTING_EFFECTS.get(self.lighting.effect_id, {}).get("dynamic", False):
            self.lighting.apply_now()

    def _on_fx_toggles_changed(self):
        self.lighting.kb_enabled = bool(self.var_fx_kb_en.get())
        self.lighting.mouse_sync_enabled = bool(self.var_fx_mouse_en.get())
        self.lighting.rainbow_override = bool(self.var_fx_rainbow.get())
        self.lighting.save_config()
        self.lighting.apply_now()

    def _pick_custom_color(self, channel_idx: int):
        cur_hex = (
            self.lighting.color1_hex if channel_idx == 1
            else self.lighting.color2_hex if channel_idx == 2
            else self.lighting.color3_hex
        )
        rgb_tuple, hex_str = colorchooser.askcolor(
            color=cur_hex,
            title=f"Farbe {channel_idx} auswählen (KB7 & SteelSeries RGB)"
        )
        if hex_str:
            self._set_channel_color(channel_idx, hex_str.upper())
            self.lighting.save_config()
            self.lighting.apply_now()
            self.lbl_lighting_status.configure(text=f"✓ Farbe {channel_idx} auf {hex_str.upper()} gesetzt!", fg="#00e575")

    def _apply_hex_entry(self, channel_idx: int):
        raw = self._color_entries[channel_idx].get().strip()
        if not raw.startswith("#"):
            raw = "#" + raw
        rgb = hex_to_rgb(raw)
        clean_hex = rgb_to_hex(rgb)
        self._set_channel_color(channel_idx, clean_hex)
        self.lighting.save_config()
        self.lighting.apply_now()
        self.lbl_lighting_status.configure(text=f"✓ Farbe {channel_idx} aktualisiert ({clean_hex})", fg="#00e575")

    def _set_channel_color(self, channel_idx: int, hex_val: str):
        if channel_idx == 1:
            self.lighting.color1_hex = hex_val
        elif channel_idx == 2:
            self.lighting.color2_hex = hex_val
        else:
            self.lighting.color3_hex = hex_val

        if channel_idx in self._color_swatches:
            self._color_swatches[channel_idx].configure(bg=hex_val, fg=self._ideal_text_fg(hex_val))
        if channel_idx in self._color_entries:
            self._color_entries[channel_idx].delete(0, tk.END)
            self._color_entries[channel_idx].insert(0, hex_val)

    def _apply_color_palette(self, h1: str, h2: str, h3: str, pal_name: str):
        self._set_channel_color(1, h1)
        self._set_channel_color(2, h2)
        self._set_channel_color(3, h3)
        self.lighting.save_config()
        self.lighting.apply_now()
        self.lbl_lighting_status.configure(text=f"✓ Palette '{pal_name}' aktiviert!", fg="#00e575")

    def _on_apply_lighting_clicked(self):
        self.lighting.save_config()
        ok = self.lighting.apply_now()
        if ok:
            self.lbl_lighting_status.configure(text="✓ Leuchteffekt & Farben an KB7 & Maus gesendet!", fg="#00e575")
        else:
            self.lbl_lighting_status.configure(text="[!] Übertragung abgeschlossen (prüfe Verbindung)", fg=COLOR_ACCENT_ALT)

    def _schedule_rgb_preview_update(self, groups, key_offsets, mouse_rgb):
        if not self.running or self.active_tab != "lighting":
            return
        self.root.after(0, lambda g=list(groups), k=dict(key_offsets), m=mouse_rgb: self._draw_rgb_preview(g, k, m))

    def _draw_rgb_preview(
        self,
        groups: List[Tuple[int, int, int]],
        key_offsets: Dict[int, Tuple[int, int, int]],
        mouse_rgb: Tuple[int, int, int],
    ):
        if not hasattr(self, "canvas_rgb_preview"):
            return
        c = self.canvas_rgb_preview
        c.delete("all")
        w = max(460, c.winfo_width())
        h = 150

        # Keyboard chassis outline (left 74% of canvas)
        kb_x0, kb_y0 = 14, 12
        kb_w = int(w * 0.72)
        kb_h = h - 24
        c.create_rectangle(kb_x0, kb_y0, kb_x0 + kb_w, kb_y0 + kb_h, fill="#0c1018", outline="#30363d", width=2)

        # Draw 7 Planar RGB Zones (Rows/Groups 0..6)
        row_h = (kb_h - 16) / 7.0
        zone_labels = [
            "G0: F-Tasten & Esc",
            "G1: Zahlenreihe 1-0",
            "G2: QWERTZ-Reihe",
            "G3: ASDF-Reihe",
            "G4: YXCV-Reihe",
            "G5: Strg / Leertaste",
            "G6: Underglow / Rand",
        ]
        for g_idx in range(7):
            rgb = groups[g_idx] if g_idx < len(groups) else (0, 255, 102)
            col_hex = rgb_to_hex(rgb)
            ry0 = kb_y0 + 8 + g_idx * row_h
            ry1 = ry0 + row_h - 3
            c.create_rectangle(kb_x0 + 10, ry0, kb_x0 + kb_w - 135, ry1, fill=col_hex, outline="#161b22")
            c.create_text(
                kb_x0 + 18, (ry0 + ry1) / 2,
                text=zone_labels[g_idx], anchor="w",
                fill=self._ideal_text_fg(col_hex), font=("Consolas", 7, "bold")
            )

        # Highlight WASD & Arrow Key Badges inside Keyboard Preview
        wasd_rgb = key_offsets.get(62, groups[2] if len(groups) > 2 else (0, 229, 255))
        wasd_hex = rgb_to_hex(wasd_rgb)
        c.create_rectangle(kb_x0 + kb_w - 125, kb_y0 + 12, kb_x0 + kb_w - 12, kb_y0 + 48, fill=wasd_hex, outline="#ffffff", width=1)
        c.create_text(
            kb_x0 + kb_w - 68, kb_y0 + 30,
            text="WASD ZONE", fill=self._ideal_text_fg(wasd_hex), font=("Segoe UI", 8, "bold")
        )

        arr_rgb = key_offsets.get(198, groups[5] if len(groups) > 5 else (255, 0, 128))
        arr_hex = rgb_to_hex(arr_rgb)
        c.create_rectangle(kb_x0 + kb_w - 125, kb_y0 + 54, kb_x0 + kb_w - 12, kb_y0 + 90, fill=arr_hex, outline="#ffffff", width=1)
        c.create_text(
            kb_x0 + kb_w - 68, kb_y0 + 72,
            text="PFEILTASTEN", fill=self._ideal_text_fg(arr_hex), font=("Segoe UI", 8, "bold")
        )

        # Mini LCD badge on top-right of keyboard
        c.create_rectangle(kb_x0 + kb_w - 125, kb_y0 + 96, kb_x0 + kb_w - 12, kb_y0 + kb_h - 8, fill="#06152d", outline="#00d2ff", width=1)
        c.create_text(kb_x0 + kb_w - 68, kb_y0 + kb_h - 20, text="4.3\" TFT LCD", fill="#00d2ff", font=("Consolas", 7, "bold"))

        # SteelSeries Mouse Preview on the right side
        ms_x0 = kb_x0 + kb_w + 16
        ms_x1 = w - 14
        ms_cx = (ms_x0 + ms_x1) / 2
        ms_hex = rgb_to_hex(mouse_rgb)

        c.create_oval(ms_cx - 34, kb_y0 + 14, ms_cx + 34, kb_y0 + kb_h - 18, fill="#10151f", outline=ms_hex, width=3)
        c.create_oval(ms_cx - 22, kb_y0 + 52, ms_cx + 22, kb_y0 + kb_h - 28, fill=ms_hex, outline="")
        c.create_rectangle(ms_cx - 4, kb_y0 + 22, ms_cx + 4, kb_y0 + 38, fill=ms_hex, outline="#ffffff")
        c.create_text(ms_cx, kb_y0 + kb_h - 6, text="🖱️ SteelSeries RGB", fill=ms_hex, font=("Segoe UI", 8, "bold"))

    # =========================================================================
    # TAB 3: WIDGETS & DISPLAY PAGES
    # =========================================================================

    def _build_widgets_tab(self, parent: tk.Frame):
        content = tk.Frame(parent, bg=COLOR_BG_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        content.pack(fill=tk.BOTH, expand=True, pady=4)

        # Header controls
        ctrl_bar = tk.Frame(content, bg=COLOR_BG_CARD)
        ctrl_bar.pack(fill=tk.X, padx=16, pady=16)

        tk.Label(ctrl_bar, text="SELECT DISPLAY PAGE:", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD).pack(side=tk.LEFT, padx=(0, 8))

        self.page_var = tk.IntVar(value=1)
        page_labels = [
            (1, "Page 1 (Home / 12 Kacheln)"),
            (2, "Page 2 (Numpad)"),
            (3, "Page 3 (🎛️ Smart Stream Deck / 12× 1x1)"),
        ]
        for p, p_lbl in page_labels:
            btn_p = tk.Radiobutton(
                ctrl_bar, text=p_lbl, variable=self.page_var, value=p,
                font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
                selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
                command=self._on_page_changed
            )
            btn_p.pack(side=tk.LEFT, padx=6)

        # Template Presets
        lbl_tmpl = tk.Label(content, text="1-CLICK LAYOUT TEMPLATES:", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD)
        lbl_tmpl.pack(anchor="w", padx=16, pady=(8, 6))

        tmpl_row = tk.Frame(content, bg=COLOR_BG_CARD)
        tmpl_row.pack(fill=tk.X, padx=16, pady=4)

        templates = [
            ("streamdeck", "🎛️ Smart Stream Deck (12× 1x1)", "#00e575", "#000000"),
            ("dashboard", "⚡ Power Dashboard", COLOR_ACCENT, "#000000"),
            ("factory", "↺ Werkseinstellung", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("telemetry", "📊 Telemetrie (12× 1x1 Mini)", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("productivity", "💼 Productivity", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("multimedia", "🎵 Media Controls", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("gaming", "🎮 Gaming & Discord", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("obs", "🎥 OBS Studio", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("empty", "🧹 Clean (Leere Kacheln)", "#2e151b", COLOR_MUTE_ACTIVE),
        ]
        for tmpl_name, label, bg_col, fg_col in templates:
            btn_t = tk.Button(
                tmpl_row, text=label, font=("Segoe UI", 9, "bold" if tmpl_name == "dashboard" else "normal"),
                bg=bg_col, fg=fg_col, bd=0, padx=10, pady=6, cursor="hand2",
                command=lambda t=tmpl_name: self._apply_template(t)
            )
            btn_t.pack(side=tk.LEFT, padx=(0, 6))

        # Current Page Slots List
        lbl_cur = tk.Label(content, text="CONFIGURED SLOTS ON PAGE:", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        lbl_cur.pack(anchor="w", padx=16, pady=(16, 6))

        self.tree_slots = ttk.Treeview(content, columns=("slot", "type", "appid", "name", "cat"), show="headings", height=12)
        self.tree_slots.heading("slot", text="Slot")
        self.tree_slots.heading("type", text="Type")
        self.tree_slots.heading("appid", text="AppID")
        self.tree_slots.heading("name", text="Widget Name")
        self.tree_slots.heading("cat", text="Category")

        self.tree_slots.column("slot", width=60, anchor="center")
        self.tree_slots.column("type", width=70, anchor="center")
        self.tree_slots.column("appid", width=80, anchor="center")
        self.tree_slots.column("name", width=260)
        self.tree_slots.column("cat", width=160)

        self.tree_slots.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # Slot Customizer Control Bar
        edit_bar = tk.Frame(content, bg=COLOR_BG_CARD)
        edit_bar.pack(fill=tk.X, padx=16, pady=(0, 16))

        tk.Label(edit_bar, text="KACHEL ANPASSEN:", font=("Segoe UI", 9, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD).pack(side=tk.LEFT, padx=(0, 8))

        self.cb_slot_idx = ttk.Combobox(edit_bar, values=[f"Slot {i}" for i in range(12)], state="readonly", width=8)
        self.cb_slot_idx.current(0)
        self.cb_slot_idx.pack(side=tk.LEFT, padx=4)

        # Build widget choices
        widget_choices = []
        self._widget_id_map = {}
        for app_id, w in sorted(WIDGET_CATALOG.items(), key=lambda x: (x[1].category, x[1].name)):
            lbl = f"[{w.category}] {w.name}"
            widget_choices.append(lbl)
            self._widget_id_map[lbl] = app_id

        self.cb_widget_select = ttk.Combobox(edit_bar, values=widget_choices, state="readonly", width=38)
        if widget_choices:
            self.cb_widget_select.current(0)
        self.cb_widget_select.pack(side=tk.LEFT, padx=8)

        btn_assign = tk.Button(
            edit_bar, text="Kachel zuweisen", font=("Segoe UI", 9, "bold"),
            bg=COLOR_ACCENT, fg="#000000", bd=0, padx=14, pady=4, cursor="hand2",
            command=self._on_assign_widget_clicked
        )
        btn_assign.pack(side=tk.LEFT, padx=4)

        def _on_tree_select(event):
            selected = self.tree_slots.selection()
            if selected:
                vals = self.tree_slots.item(selected[0], "values")
                if vals:
                    slot_str = vals[0]  # "Slot 3"
                    try:
                        idx = int(slot_str.split()[1])
                        if 0 <= idx < 12:
                            self.cb_slot_idx.current(idx)
                    except Exception:
                        pass
        self.tree_slots.bind("<<TreeviewSelect>>", _on_tree_select)

    def _on_assign_widget_clicked(self):
        p = self.page_var.get()
        slot_str = self.cb_slot_idx.get()
        slot_idx = int(slot_str.split()[1])
        selected_label = self.cb_widget_select.get()
        app_id = self._widget_id_map.get(selected_label, 0)

        try:
            if self.daemon and self.daemon.device:
                with self.daemon.lock:
                    self.daemon.device.assign_widget(p - 1, slot_idx, app_id)
            elif self.client and self.hw_connected:
                self.client.assign_widget(page=p, slot=slot_idx, app_id=app_id)
            else:
                with KB7Device() as dev:
                    dev.assign_widget(p - 1, slot_idx, app_id)

            time.sleep(0.05)
            self.refresh_slots_view()
            messagebox.showinfo("Success", f"Widget '{selected_label}' assigned to Page {p}, Slot {slot_idx}!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign widget: {e}")

    def _on_page_changed(self):
        p = self.page_var.get()
        if self.daemon and self.daemon.device:
            try:
                with self.daemon.lock:
                    self.daemon.device.set_active_page(p)
            except Exception:
                pass
        elif self.client and self.hw_connected:
            try:
                self.client.set_page(p)
            except Exception:
                pass
        else:
            try:
                with KB7Device() as dev:
                    dev.set_active_page(p)
            except Exception:
                pass
        self.refresh_slots_view()

    def _apply_template(self, tmpl_name: str):
        p = self.page_var.get()
        try:
            if self.daemon and self.daemon.device:
                with self.daemon.lock:
                    self.daemon.device.apply_template(p - 1, tmpl_name)
            elif self.client and self.hw_connected:
                self.client.apply_template(page=p, template_name=tmpl_name)
            else:
                with KB7Device() as dev:
                    dev.apply_template(p - 1, tmpl_name)

            time.sleep(0.05)
            self.refresh_slots_view()
            messagebox.showinfo("Success", f"Layout '{tmpl_name}' erfolgreich auf Seite {p} angewendet!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply template: {e}")

    def refresh_slots_view(self):
        for item in self.tree_slots.get_children():
            self.tree_slots.delete(item)

        p = self.page_var.get()
        slots = None

        if self.daemon and self.daemon.device:
            try:
                with self.daemon.lock:
                    settings = self.daemon.device.get_lcd_settings()
                    slots = []
                    for i, (w_type, w_id) in enumerate(settings.widget_slots):
                        p_num = (i // 12) + 1
                        s_idx = i % 12
                        if p_num != p:
                            continue
                        w_def = lookup_widget(w_id)
                        slots.append({
                            "slot": s_idx, "type": w_type, "app_id": w_id,
                            "name": w_def.name, "category": w_def.category
                        })
            except Exception as e:
                print(f"[!] Error reading slots: {e}")
        elif self.client and self.hw_connected:
            try:
                slots = self.client.get_slots(page=p)
            except Exception:
                pass
        else:
            try:
                with KB7Device() as dev:
                    settings = dev.get_lcd_settings()
                    slots = []
                    for i, (w_type, w_id) in enumerate(settings.widget_slots):
                        p_num = (i // 12) + 1
                        s_idx = i % 12
                        if p_num != p:
                            continue
                        w_def = lookup_widget(w_id)
                        slots.append({
                            "slot": s_idx, "type": w_type, "app_id": w_id,
                            "name": w_def.name, "category": w_def.category
                        })
            except Exception:
                pass

        if slots:
            for s in slots:
                self.tree_slots.insert("", tk.END, values=(
                    f"Slot {s['slot']}", s["type"], s["app_id"], s["name"], s["category"]
                ))

    # =========================================================================
    # TAB 4: HARDWARE & TOUCH LOGS
    # =========================================================================

    def _build_hardware_tab(self, parent: tk.Frame):
        content = tk.Frame(parent, bg=COLOR_BG_CARD, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        content.pack(fill=tk.BOTH, expand=True, pady=4)

        info_box = tk.Frame(content, bg=COLOR_BG_CARD)
        info_box.pack(fill=tk.X, padx=16, pady=16)

        tk.Label(info_box, text="HARDWARE SPECIFICATIONS & ENDPOINTS", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD).pack(anchor="w")

        info_text = (
            "• USB VID/PID: 0x10F5 : 0x5038 (Turtle Beach / Roccat)\n"
            "• Dual-MCU Architecture: Sonix SNC73xx ARM (Display/Host) + Artery AT423 (Analog Matrix)\n"
            "• Display: 4.3\" Color TFT LCD, 800x480 WVGA, 16-Bit RGB565 Little-Endian\n"
            "• Display Endpoint: Interface mi_01 (Usage Page 0xFF00, Usage 0x0001)\n"
            "• Touch Endpoint: Interface mi_02 / COL04 (Usage Page 0xFF02, Report ID 0x33)"
        )
        tk.Label(info_box, text=info_text, font=("Consolas", 9), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD, justify=tk.LEFT).pack(anchor="w", pady=6)

        # Touch Log Area
        tk.Label(content, text="REAL-TIME TOUCH DIGITIZER EVENT STREAM:", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD).pack(anchor="w", padx=16, pady=(12, 4))

        self.txt_log = tk.Text(content, bg="#080c14", fg="#00e5ff", font=("Consolas", 9), bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

    def _append_log(self, text: str):
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def _start_background_workers(self):
        """Dedicated background thread for WASAPI COM audio polling, preventing GUI freezes."""
        def audio_poller():
            try:
                import comtypes
                comtypes.CoInitialize()
            except Exception:
                pass

            last_vol = -1
            last_mute = None
            last_apps_sig = None

            while self.running:
                if self.active_tab == "mixer":
                    try:
                        dev = self.mixer.get_default_device()
                        apps = self.mixer.get_grouped_apps()
                        v = dev.volume if dev else -1
                        m = dev.muted if dev else None
                        sig = tuple((a.name, a.volume, a.muted) for a in apps)

                        if v != last_vol or m != last_mute or sig != last_apps_sig:
                            last_vol, last_mute, last_apps_sig = v, m, sig
                            self.root.after(0, lambda d=dev, a=apps: self._apply_audio_state(d, a))
                    except Exception:
                        pass
                    time.sleep(1.2)
                else:
                    if self.active_tab == "streamdeck" and hasattr(self, "lbl_detected_stream"):
                        try:
                            wins = scan_stream_windows()
                            if wins:
                                w0 = wins[0]
                                txt = f"● [{w0.platform}] {w0.clean_title[:45]}"
                                col = "#00e575" if "TWITCH" in w0.platform or "OBS" in w0.platform else "#00e5ff"
                            else:
                                txt = "○ Kein Browser-Stream offen (nutzt Desktop-Vollbild als Quelle)"
                                col = COLOR_TEXT_MUTED
                            self.root.after(0, lambda t=txt, c=col: self.lbl_detected_stream.configure(text=t, fg=c))
                        except Exception:
                            pass
                    time.sleep(2.0)

        threading.Thread(target=audio_poller, daemon=True).start()

    def on_close(self):
        self.running = False
        if hasattr(self, "lighting") and self.lighting:
            try:
                self.lighting.stop()
            except Exception:
                pass
        if self.steelseries:
            try:
                self.steelseries.stop()
            except Exception:
                pass
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        if self.daemon:
            try:
                self.daemon.stop()
            except Exception:
                pass
        self.root.destroy()


def run_app():
    root = tk.Tk()
    app = KB7CommandCenterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    run_app()
