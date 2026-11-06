"""
Turtle Beach KB7 - Windows Audio Mixer GUI.

A modern, dark-themed Windows Sound Display & Volume Controller.
Provides per-application volume sliders across all active audio devices
(including SteelSeries Sonar, Voicemeeter, and USB endpoints) and integrates
with the Turtle Beach KB7 hardware daemon for rotary dial and touch control.
"""

import sys
import time
import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List, Optional

from .audio_mixer import UniversalAudioMixer, AppGroup, AudioDeviceItem
from .client import KB7Client


# Color Palette (Dark Cyber / Turtle Beach inspired)
COLOR_BG_DARK = "#12151b"
COLOR_BG_CARD = "#1a1f29"
COLOR_BG_HOVER = "#242c3b"
COLOR_ACCENT = "#00d2ff"      # Cyan accent
COLOR_ACCENT_ALT = "#ffaa00"  # Gold accent
COLOR_TEXT_MAIN = "#f0f4f8"
COLOR_TEXT_MUTED = "#8290a5"
COLOR_MUTE_ACTIVE = "#ff4444" # Red for muted
COLOR_MUTE_INACTIVE = "#2a3547"
COLOR_BORDER = "#2b3444"


class SoundMixerApp:
    """
    Tkinter-based Universal Sound Mixer with KB7 Daemon synchronization.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Turtle Beach KB7 - Universal Audio Mixer")
        self.root.geometry("880x560")
        self.root.minsize(700, 480)
        self.root.configure(bg=COLOR_BG_DARK)

        # Audio engine
        self.mixer = UniversalAudioMixer()
        self.active_device: Optional[AudioDeviceItem] = None
        self.app_groups: List[AppGroup] = []
        self.selected_target: Optional[str] = "Master" # Selected for KB7 knob

        # KB7 Client connection
        self.client: Optional[KB7Client] = None
        self.kb7_connected = False
        self._init_kb7_client()

        # UI State tracking (to avoid slider jitter during drags)
        self.is_dragging = False
        self.app_widgets: Dict[str, Dict[str, Any]] = {}

        # Build UI layout
        self._build_ui()

        # Initial load
        self.refresh_audio_state()

        # Start periodic background sync (500 ms)
        self.root.after(500, self._poll_updates)

    def _init_kb7_client(self):
        """Attempts to connect to the local KB7 daemon for knob/touch binding."""
        try:
            self.client = KB7Client()
            if self.client.connect(timeout=0.5):
                self.kb7_connected = True
                print("[+] SoundMixer connected to KB7 Daemon.")
                # Subscribe to touch events
                @self.client.on_touch()
                def on_touch_event(event):
                    self._handle_kb7_touch(event)
        except Exception:
            self.client = None
            self.kb7_connected = False

    def _handle_kb7_touch(self, event: Dict[str, Any]):
        """Reacts to touch events from the KB7 screen."""
        gesture = event.get("gesture")
        slot = event.get("slot_id")
        # Example: Slot 0 = Mute Master, Slot 1 = Next App
        if gesture == "tap":
            if slot == 0:
                self.root.after(0, self.toggle_master_mute)
            elif slot == 1:
                self.root.after(0, self._cycle_selected_target)

    def _cycle_selected_target(self):
        """Cycles active channel selected for knob control."""
        targets = ["Master"] + [a.name for a in self.app_groups]
        if self.selected_target in targets:
            idx = (targets.index(self.selected_target) + 1) % len(targets)
            self.select_target(targets[idx])

    def _build_ui(self):
        """Builds modern Tkinter layout."""
        # Top Header Bar
        header = tk.Frame(self.root, bg=COLOR_BG_CARD, height=60, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        header.pack(fill=tk.X, side=tk.TOP, padx=12, pady=(12, 6))

        # Title & Subtitle
        title_frame = tk.Frame(header, bg=COLOR_BG_CARD)
        title_frame.pack(side=tk.LEFT, padx=16, pady=10)

        lbl_title = tk.Label(
            title_frame, text="🔊 Windows Sound Mixer",
            font=("Segoe UI", 14, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            title_frame, text="Universal multi-endpoint volume controller for KB7",
            font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD
        )
        lbl_sub.pack(anchor="w")

        # Hardware Status Pill
        self.lbl_kb7_status = tk.Label(
            header,
            text="● KB7 Connected" if self.kb7_connected else "○ KB7 Offline",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_ACCENT if self.kb7_connected else COLOR_TEXT_MUTED,
            bg=COLOR_BG_CARD,
            padx=10, pady=4
        )
        self.lbl_kb7_status.pack(side=tk.RIGHT, padx=16)

        # Main Content Area
        content = tk.Frame(self.root, bg=COLOR_BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # LEFT: Master Volume Card
        self.master_card = tk.Frame(content, bg=COLOR_BG_CARD, width=200, bd=0, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.master_card.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 6), pady=0)
        self.master_card.pack_propagate(False)

        lbl_m_title = tk.Label(self.master_card, text="MASTER OUTPUT", font=("Segoe UI", 10, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_CARD)
        lbl_m_title.pack(anchor="center", pady=(16, 4))

        self.lbl_master_dev = tk.Label(self.master_card, text="Default Device", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD, wraplength=170)
        self.lbl_master_dev.pack(anchor="center", pady=(0, 16))

        # Master Slider
        self.master_slider = tk.Scale(
            self.master_card, from_=100, to=0, orient=tk.VERTICAL,
            length=240, width=24, showvalue=False,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MAIN,
            troughcolor=COLOR_BG_DARK, activebackground=COLOR_ACCENT,
            highlightthickness=0, bd=0,
            command=self._on_master_slide
        )
        self.master_slider.pack(anchor="center", pady=6)

        self.lbl_master_pct = tk.Label(self.master_card, text="100%", font=("Segoe UI", 14, "bold"), fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD)
        self.lbl_master_pct.pack(anchor="center", pady=6)

        self.btn_master_mute = tk.Button(
            self.master_card, text="MUTE", font=("Segoe UI", 9, "bold"),
            bg=COLOR_MUTE_INACTIVE, fg=COLOR_TEXT_MAIN,
            activebackground=COLOR_MUTE_ACTIVE, activeforeground="#ffffff",
            bd=0, padx=16, pady=6, cursor="hand2",
            command=self.toggle_master_mute
        )
        self.btn_master_mute.pack(anchor="center", pady=(8, 16))

        # RIGHT: Applications Scrollable Grid
        app_area = tk.Frame(content, bg=COLOR_BG_DARK)
        app_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        lbl_apps_head = tk.Label(
            app_area, text="APPLICATIONS (ALL SOUND ENDPOINTS)",
            font=("Segoe UI", 10, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_DARK
        )
        lbl_apps_head.pack(anchor="w", padx=6, pady=(0, 6))

        # Scrollable Canvas
        self.canvas = tk.Canvas(app_area, bg=COLOR_BG_DARK, bd=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(app_area, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scroll_frame = tk.Frame(self.canvas, bg=COLOR_BG_DARK)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(xscrollcommand=self.scrollbar.set)

        self.canvas.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.scrollbar.pack(fill=tk.X, side=tk.BOTTOM)

    def select_target(self, name: str):
        """Highlights the selected target (Master or specific app) for knob control."""
        self.selected_target = name
        # Highlight UI cards
        if name == "Master":
            self.master_card.configure(highlightbackground=COLOR_ACCENT, highlightthickness=2)
        else:
            self.master_card.configure(highlightbackground=COLOR_BORDER, highlightthickness=1)

        for app_name, w in self.app_widgets.items():
            card = w.get("card")
            if card:
                if app_name == name:
                    card.configure(highlightbackground=COLOR_ACCENT, highlightthickness=2)
                else:
                    card.configure(highlightbackground=COLOR_BORDER, highlightthickness=1)

    def refresh_audio_state(self):
        """Queries audio system and updates UI controls."""
        try:
            self.active_device = self.mixer.get_default_device()
            self.app_groups = self.mixer.get_grouped_apps()
        except Exception as e:
            print(f"[!] Audio refresh error: {e}")
            return

        # Update Master Device Card
        if self.active_device:
            self.lbl_master_dev.configure(text=self.active_device.name)
            if not self.is_dragging:
                m_vol = self.active_device.volume
                self.master_slider.set(m_vol)
                self.lbl_master_pct.configure(text=f"{m_vol}%")

            if self.active_device.muted:
                self.btn_master_mute.configure(bg=COLOR_MUTE_ACTIVE, text="MUTED")
            else:
                self.btn_master_mute.configure(bg=COLOR_MUTE_INACTIVE, text="MUTE")

        # Update or Create App Cards
        current_names = set(a.name for a in self.app_groups)
        existing_names = set(self.app_widgets.keys())

        # Remove dead apps
        for dead in existing_names - current_names:
            w = self.app_widgets.pop(dead)
            w["card"].destroy()

        # Add or update active apps
        for app in self.app_groups:
            if app.name not in self.app_widgets:
                self._create_app_card(app)
            else:
                self._update_app_card(app)

    def _create_app_card(self, app: AppGroup):
        """Instantiates a vertical channel card for an application."""
        card = tk.Frame(
            self.scroll_frame, bg=COLOR_BG_CARD, width=130, bd=0,
            highlightthickness=2 if self.selected_target == app.name else 1,
            highlightbackground=COLOR_ACCENT if self.selected_target == app.name else COLOR_BORDER
        )
        card.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)
        card.pack_propagate(False)

        # Click card to select for knob control
        card.bind("<Button-1>", lambda e, n=app.name: self.select_target(n))

        # App Title
        lbl_name = tk.Label(
            card, text=app.name, font=("Segoe UI", 10, "bold"),
            fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD, wraplength=110
        )
        lbl_name.pack(anchor="center", pady=(12, 2))
        lbl_name.bind("<Button-1>", lambda e, n=app.name: self.select_target(n))

        # Target Device Badge
        dev_badge = app.devices[0] if app.devices else "Playback"
        lbl_dev = tk.Label(
            card, text=dev_badge[:16], font=("Segoe UI", 7),
            fg=COLOR_TEXT_MUTED, bg=COLOR_BG_CARD
        )
        lbl_dev.pack(anchor="center", pady=(0, 10))

        # Slider
        slider = tk.Scale(
            card, from_=100, to=0, orient=tk.VERTICAL,
            length=180, width=20, showvalue=False,
            bg=COLOR_BG_CARD, fg=COLOR_TEXT_MAIN,
            troughcolor=COLOR_BG_DARK, activebackground=COLOR_ACCENT,
            highlightthickness=0, bd=0,
            command=lambda v, a=app: self._on_app_slide(a, v)
        )
        slider.set(app.volume)
        slider.pack(anchor="center", pady=6)

        # Percentage
        lbl_pct = tk.Label(
            card, text=f"{app.volume}%", font=("Segoe UI", 11, "bold"),
            fg=COLOR_TEXT_MAIN, bg=COLOR_BG_CARD
        )
        lbl_pct.pack(anchor="center", pady=4)

        # Mute button
        btn_mute = tk.Button(
            card, text="MUTED" if app.muted else "MUTE",
            font=("Segoe UI", 8, "bold"),
            bg=COLOR_MUTE_ACTIVE if app.muted else COLOR_MUTE_INACTIVE,
            fg=COLOR_TEXT_MAIN, bd=0, padx=12, pady=4, cursor="hand2",
            command=lambda a=app: self._toggle_app_mute(a)
        )
        btn_mute.pack(anchor="center", pady=(6, 12))

        self.app_widgets[app.name] = {
            "card": card,
            "slider": slider,
            "lbl_pct": lbl_pct,
            "btn_mute": btn_mute,
            "lbl_dev": lbl_dev,
            "app": app,
        }

    def _update_app_card(self, app: AppGroup):
        """Updates values on an existing app card."""
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
        """Invoked when user moves the Master slider."""
        self.is_dragging = True
        v = int(val)
        self.lbl_master_pct.configure(text=f"{v}%")
        if self.active_device:
            self.active_device.volume = v
        self.root.after(100, self._clear_drag)

    def _on_app_slide(self, app: AppGroup, val: str):
        """Invoked when user moves an app volume slider."""
        self.is_dragging = True
        v = int(val)
        w = self.app_widgets.get(app.name)
        if w:
            w["lbl_pct"].configure(text=f"{v}%")
        app.volume = v
        self.root.after(100, self._clear_drag)

    def _clear_drag(self):
        self.is_dragging = False

    def toggle_master_mute(self):
        """Toggles mute on master device."""
        if self.active_device:
            new_state = self.active_device.toggle_mute()
            if new_state:
                self.btn_master_mute.configure(bg=COLOR_MUTE_ACTIVE, text="MUTED")
            else:
                self.btn_master_mute.configure(bg=COLOR_MUTE_INACTIVE, text="MUTE")

    def _toggle_app_mute(self, app: AppGroup):
        """Toggles mute on application."""
        new_state = app.toggle_mute()
        w = self.app_widgets.get(app.name)
        if w:
            if new_state:
                w["btn_mute"].configure(bg=COLOR_MUTE_ACTIVE, text="MUTED")
            else:
                w["btn_mute"].configure(bg=COLOR_MUTE_INACTIVE, text="MUTE")

    def _poll_updates(self):
        """Periodic sync to detect external volume changes."""
        self.refresh_audio_state()
        self.root.after(500, self._poll_updates)


def run_mixer_gui():
    """Launches the Windows Sound Mixer GUI."""
    root = tk.Tk()
    app = SoundMixerApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if app.client:
            app.client.close()


if __name__ == "__main__":
    run_mixer_gui()
