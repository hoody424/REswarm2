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
from tkinter import ttk, filedialog, messagebox
from typing import Dict, Any, List, Optional
from PIL import Image, ImageTk

from .audio_mixer import UniversalAudioMixer, AppGroup, AudioDeviceItem
from .client import KB7Client
from .daemon import KB7Daemon
from .theme_generator import THEME_PRESETS
from .image import convert_to_rgb565
from .widgets import WIDGET_CATALOG, LAYOUT_TEMPLATES, lookup_widget
from .device import KB7Device, SLOT_BACKGROUND
from .steelseries import SteelSeriesSync, THEME_RGB_MAP

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
        self.active_tab = "mixer"
        self._ensure_hardware_service()

        # SteelSeries Mouse RGB Synchronization
        self.steelseries: Optional[SteelSeriesSync] = None
        try:
            self.steelseries = SteelSeriesSync()
            self.steelseries.start()
        except Exception as e:
            print(f"[!] SteelSeries init warning: {e}")

        # Theme & Wallpaper State
        self.selected_theme_name = "tactical_hud"
        self.preview_image_tk: Optional[ImageTk.PhotoImage] = None
        self.custom_image_path: Optional[str] = None

        # Build Navigation & Main Views
        self._build_header()
        self._build_tabs()

        # Initial Audio & Display Refresh (Non-blocking background thread)
        self.refresh_audio_state()
        self.refresh_display_settings()

        # Start non-blocking background workers
        self._start_background_workers()

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
        """Logs and handles touch events from the display."""
        gesture = ev.get("gesture")
        slot = ev.get("slot_id")
        line = f"[{time.strftime('%H:%M:%S')}] Touch: {gesture:<11} | Slot={slot:2d} | Coord=({ev.get('x')}, {ev.get('y')})"
        self.root.after(0, lambda: self._append_log(line))

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
            ("mixer", "🔊 Windows Sound Mixer"),
            ("themes", "🎨 Display Themes & Wallpaper"),
            ("widgets", "🧩 Widgets & Display Pages"),
            ("hardware", "⚡ Hardware & Touch Logs"),
        ]

        self.content_container = tk.Frame(self.root, bg=COLOR_BG_DARK)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        for key, title in tabs:
            btn = tk.Button(
                tab_nav, text=title, font=("Segoe UI", 10, "bold"),
                bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED, bd=0, padx=16, pady=8,
                cursor="hand2", activebackground=COLOR_BG_HOVER, activeforeground=COLOR_TEXT_MAIN,
                command=lambda k=key: self.switch_tab(k)
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.tab_buttons[key] = btn

            frame = tk.Frame(self.content_container, bg=COLOR_BG_DARK)
            self.tab_frames[key] = frame

        # Build individual views
        self._build_mixer_tab(self.tab_frames["mixer"])
        self._build_themes_tab(self.tab_frames["themes"])
        self._build_widgets_tab(self.tab_frames["widgets"])
        self._build_hardware_tab(self.tab_frames["hardware"])

        self.switch_tab("mixer")

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

        lbl_prev_title = tk.Label(right, text="DISPLAY PREVIEW (800 x 480 WVGA)", font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        lbl_prev_title.pack(anchor="w", padx=20, pady=(16, 8))

        # Preview Image Frame
        self.lbl_preview = tk.Label(right, bg="#080c14", bd=0, highlightthickness=2, highlightbackground=COLOR_BORDER)
        self.lbl_preview.pack(padx=20, pady=8)

        # Options bar: Switch to clean page & Reset to factory
        opt_bar = tk.Frame(right, bg=COLOR_BG_CARD)
        opt_bar.pack(fill=tk.X, padx=20, pady=(4, 6))

        self.var_switch_clean_page = tk.BooleanVar(value=False)
        cb_clean = tk.Checkbutton(
            opt_bar, text="Nach Upload auf leere Seite 5 wechseln",
            variable=self.var_switch_clean_page,
            font=("Segoe UI", 9), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
            selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD, activeforeground=COLOR_TEXT_MAIN
        )
        cb_clean.pack(side=tk.LEFT)

        btn_reset_theme = tk.Button(
            opt_bar, text="↺ Werkseinstellung Hintergrund", font=("Segoe UI", 8),
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

            # Scale to fit GUI preview (e.g. 520x312)
            preview_im = im.resize((520, 312), Image.Resampling.LANCZOS)
            self.preview_image_tk = ImageTk.PhotoImage(preview_im)
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
                            self.daemon.device.set_active_page(5)
                elif self.client and self.hw_connected:
                    progress_cb("Sending upload command to KB7 Daemon (please wait)...", 20)
                    preset_name = None if self.custom_image_path else self.theme_var.get()
                    self.client.apply_theme(name=preset_name, path=self.custom_image_path)
                    if self.var_switch_clean_page.get():
                        self.client.set_page(5)
                    progress_cb("Theme active and visible on KB7 display!", 100)
                else:
                    with KB7Device() as dev:
                        dev.upload_theme(im, progress_callback=progress_cb)
                        if self.var_switch_clean_page.get():
                            dev.set_active_page(5)

                msg = "[+] Theme active on KB7 display!"
                if self.var_switch_clean_page.get():
                    msg += " (Switched to clean Page 5)"
                    self.page_var.set(5)

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
        """Resets the keyboard screen to built-in factory wallpaper."""
        try:
            if self.daemon and self.daemon.device:
                with self.daemon.lock:
                    self.daemon.device.set_background_mode(0)
                    self.daemon.device.refresh_screen()
            elif self.client and self.hw_connected:
                self.client.set_background_mode(0)
                self.client.refresh_screen()
            else:
                with KB7Device() as dev:
                    dev.set_background_mode(0)
                    dev.refresh_screen()
            self.lbl_upload_status.configure(text="[+] Restored factory default wallpaper.", fg=COLOR_ACCENT)
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
        for p in range(1, 6):
            btn_p = tk.Radiobutton(
                ctrl_bar, text=f"Page {p}", variable=self.page_var, value=p,
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
            ("dashboard", "⚡ Power Dashboard", COLOR_ACCENT, "#000000"),
            ("factory", "↺ Werkseinstellung", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
            ("telemetry", "📊 Telemetrie", COLOR_BG_HOVER, COLOR_TEXT_MAIN),
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

        self.tree_slots = ttk.Treeview(content, columns=("slot", "type", "appid", "name", "cat"), show="headings", height=8)
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

        self.cb_slot_idx = ttk.Combobox(edit_bar, values=[f"Slot {i}" for i in range(7)], state="readonly", width=8)
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
                        if 0 <= idx < 7:
                            self.cb_slot_idx.current(idx)
                    except Exception:
                        pass
        self.tree_slots.bind("<<TreeviewSelect>>", _on_tree_select)

        self.refresh_slots_view()

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
                        p_num = (i // 7) + 1
                        s_idx = i % 7
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
                        p_num = (i // 7) + 1
                        s_idx = i % 7
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
                    time.sleep(2.0)

        threading.Thread(target=audio_poller, daemon=True).start()

    def on_close(self):
        self.running = False
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
