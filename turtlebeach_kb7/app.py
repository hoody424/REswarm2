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
        self._ensure_hardware_service()

        # Theme & Wallpaper State
        self.selected_theme_name = "tactical_hud"
        self.preview_image_tk: Optional[ImageTk.PhotoImage] = None
        self.custom_image_path: Optional[str] = None

        # Build Navigation & Main Views
        self._build_header()
        self._build_tabs()

        # Initial Audio & Display Refresh
        self.refresh_audio_state()
        self.refresh_display_settings()

        # Start background polling
        self.root.after(500, self._poll_updates)

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
        for key, frame in self.tab_frames.items():
            if key == active_key:
                frame.pack(fill=tk.BOTH, expand=True)
                self.tab_buttons[key].configure(bg=COLOR_TAB_ACTIVE, fg=COLOR_ACCENT)
            else:
                frame.pack_forget()
                self.tab_buttons[key].configure(bg=COLOR_BG_CARD, fg=COLOR_TEXT_MUTED)

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
        try:
            self.active_device = self.mixer.get_default_device()
            self.app_groups = self.mixer.get_grouped_apps()
        except Exception:
            return

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
        left = tk.Frame(content, bg=COLOR_BG_CARD, width=320, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left.pack_propagate(False)

        lbl_presets = tk.Label(left, text="DISPLAY THEMES & HUD PRESETS", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD)
        lbl_presets.pack(anchor="w", padx=16, pady=(16, 12))

        # Radio buttons for presets
        self.theme_var = tk.StringVar(value="tactical_hud")
        for key, label, desc in [
            ("tactical_hud", "Tactical HUD Cockpit", "Cyberpunk Cyan & Gold Telemetry"),
            ("audiophile_dark", "Audiophile Studio Deck", "Analog VU Meters & Brushed Gold"),
            ("neon_cyberpunk", "Neon Cyberpunk", "Synthwave Magenta/Cyan Perspective"),
        ]:
            f_opt = tk.Frame(left, bg=COLOR_BG_CARD)
            f_opt.pack(fill=tk.X, padx=16, pady=4)

            rb = tk.Radiobutton(
                f_opt, text=label, variable=self.theme_var, value=key,
                font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD,
                selectcolor=COLOR_BG_DARK, activebackground=COLOR_BG_CARD,
                command=self._on_theme_selected
            )
            rb.pack(anchor="w")

            lbl_d = tk.Label(f_opt, text=desc, font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
            lbl_d.pack(anchor="w", padx=20)

        # Custom File Button
        btn_custom = tk.Button(
            left, text="📁 Choose Custom Image File...", font=("Segoe UI", 9),
            bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=12, pady=6, cursor="hand2",
            command=self._browse_custom_image
        )
        btn_custom.pack(anchor="w", padx=16, pady=(12, 16))

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

        # Progress bar & Upload Button
        self.progress_bar = ttk.Progressbar(right, orient=tk.HORIZONTAL, length=480, mode="determinate")
        self.progress_bar.pack(padx=20, pady=(12, 6))

        self.btn_upload = tk.Button(
            right, text="⚡ APPLY THEME TO KB7 DISPLAY", font=("Segoe UI", 11, "bold"),
            bg=COLOR_ACCENT, fg="#000000", activebackground="#00e5ff", activeforeground="#000000",
            bd=0, padx=24, pady=10, cursor="hand2", command=self._upload_selected_theme
        )
        self.btn_upload.pack(padx=20, pady=(6, 16))

        self.lbl_upload_status = tk.Label(right, text="Ready to upload.", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD)
        self.lbl_upload_status.pack(padx=20)

        # Initial Preview Render
        self._update_preview()

    def _on_theme_selected(self):
        self.custom_image_path = None
        self._update_preview()

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

                rgb565 = convert_to_rgb565(im)

                self.lbl_upload_status.configure(text="Streaming to KB7 over USB HID...")
                with KB7Device() as dev:
                    def progress_cb(sent, total):
                        pct = (sent * 100) // total
                        self.root.after(0, lambda: self._update_progress(pct, sent, total))

                    dev.upload_image(rgb565, slot_id=SLOT_BACKGROUND, progress_callback=progress_cb)

                self.root.after(0, lambda: self.lbl_upload_status.configure(text="[+] Theme active on KB7 display!", fg=COLOR_ACCENT))
            except Exception as e:
                self.root.after(0, lambda: self.lbl_upload_status.configure(text=f"[!] Upload error: {e}", fg=COLOR_MUTE_ACTIVE))
            finally:
                self.root.after(0, lambda: self.btn_upload.configure(state=tk.NORMAL))

        threading.Thread(target=worker, daemon=True).start()

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

        for tmpl_name in ["multimedia", "telemetry", "productivity", "gaming", "numpad", "obs"]:
            btn_t = tk.Button(
                tmpl_row, text=f"Apply {tmpl_name.capitalize()}", font=("Segoe UI", 9),
                bg=COLOR_BG_HOVER, fg=COLOR_TEXT_MAIN, bd=0, padx=12, pady=6, cursor="hand2",
                command=lambda t=tmpl_name: self._apply_template(t)
            )
            btn_t.pack(side=tk.LEFT, padx=(0, 8))

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

        self.tree_slots.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        self.refresh_slots_view()

    def _on_page_changed(self):
        p = self.page_var.get()
        if self.client and self.hw_connected:
            try:
                self.client.set_page(p)
            except Exception:
                pass
        self.refresh_slots_view()

    def _apply_template(self, tmpl_name: str):
        p = self.page_var.get()
        if self.client and self.hw_connected:
            try:
                self.client.apply_template(page=p, template_name=tmpl_name)
                time.sleep(0.1)
                self.refresh_slots_view()
                messagebox.showinfo("Success", f"Applied template '{tmpl_name}' to Page {p}!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to apply template: {e}")

    def refresh_slots_view(self):
        for item in self.tree_slots.get_children():
            self.tree_slots.delete(item)

        p = self.page_var.get()
        if self.client and self.hw_connected:
            try:
                slots = self.client.get_slots(page=p)
                for s in slots:
                    self.tree_slots.insert("", tk.END, values=(
                        f"Slot {s['slot']}", s["type"], s["app_id"], s["name"], s["category"]
                    ))
            except Exception:
                pass

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

    def _poll_updates(self):
        self.refresh_audio_state()
        self.root.after(500, self._poll_updates)

    def on_close(self):
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
