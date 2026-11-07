"""
SteelSeries GameSense RGB Synchronization Module for Turtle Beach KB7.

Synchronizes illumination between the SteelSeries mouse (e.g. Aerox 3 Wireless, Rival, Prime)
and the Turtle Beach Command Series KB7 keyboard display themes.
Communicates via the official SteelSeries GameSense REST API on 127.0.0.1 (coreProps.json).
"""

import os
import json
import time
import urllib.request
import urllib.error
import threading
from typing import Optional, Tuple, Dict

GAME_NAME = "KB7_COMMAND"
GAME_DISPLAY = "KB7 Command Center"

# Theme signature illumination colors (R, G, B)
THEME_RGB_MAP: Dict[str, Tuple[int, int, int]] = {
    "matrix_cyberdeck": (0, 255, 102),     # Phosphor Green
    "toxic_radar": (57, 255, 20),          # Toxic Neon Green
    "biohazard_reactor": (0, 255, 136),    # Radiant Emerald Plasma
    "emerald_synthwave": (0, 255, 120),    # Synthwave Emerald
    "tactical_hud": (0, 229, 255),         # Cyberpunk Cyan
    "audiophile_dark": (230, 165, 30),     # Studio Gold
    "neon_cyberpunk": (255, 0, 128),       # Neon Magenta
}


class SteelSeriesSync:
    """Manages connection and RGB illumination updates via SteelSeries GameSense."""

    def __init__(self):
        self.address: Optional[str] = None
        self.connected = False
        self.running = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self.current_rgb: Tuple[int, int, int] = (0, 255, 102)
        self.auto_sync_theme = True

        self._discover_address()

    def _discover_address(self) -> bool:
        """Finds GameSense address from coreProps.json."""
        core_props_path = os.path.join(
            os.environ.get("PROGRAMDATA", r"C:\ProgramData"),
            "SteelSeries", "SteelSeries Engine 3", "coreProps.json"
        )
        if not os.path.exists(core_props_path):
            return False

        try:
            with open(core_props_path, "r", encoding="utf-8") as f:
                props = json.load(f)
            raw_addr = props.get("address")
            if raw_addr:
                self.address = f"http://{raw_addr}"
                return True
        except Exception:
            pass
        return False

    def is_available(self) -> bool:
        """Checks if SteelSeries Engine is present and accessible."""
        if not self.address and not self._discover_address():
            return False
        try:
            req = urllib.request.Request(
                f"{self.address}/game_metadata",
                data=json.dumps({"game": GAME_NAME, "game_display_name": GAME_DISPLAY}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start(self) -> bool:
        """Initializes game registration and starts heartbeat loop."""
        if not self.address and not self._discover_address():
            return False

        try:
            # 1. Register metadata
            meta_data = {
                "game": GAME_NAME,
                "game_display_name": GAME_DISPLAY,
                "icon_color_id": 5
            }
            self._post("/game_metadata", meta_data)

            # 2. Bind default mouse event
            self._bind_mouse_event(self.current_rgb[0], self.current_rgb[1], self.current_rgb[2])

            self.connected = True
            self.running = True

            # 3. Start background heartbeat thread (every 6 seconds)
            self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._heartbeat_thread.start()

            print(f"[+] SteelSeries GameSense connected at {self.address}")
            return True
        except Exception as e:
            print(f"[!] SteelSeries GameSense start failed: {e}")
            self.connected = False
            return False

    def _bind_mouse_event(self, r: int, g: int, b: int):
        """Binds RGB color handler for mouse zones."""
        bind_payload = {
            "game": GAME_NAME,
            "event": "SYNC_RGB",
            "handlers": [
                {
                    "device-type": "mouse",
                    "zone": "all",
                    "mode": "color",
                    "color": {"red": r, "green": g, "blue": b}
                }
            ]
        }
        self._post("/bind_game_event", bind_payload)

    def set_color(self, r: int, g: int, b: int) -> bool:
        """Sets SteelSeries mouse LED illumination to RGB color."""
        self.current_rgb = (r, g, b)
        if not self.connected:
            if not self.start():
                return False

        try:
            self._bind_mouse_event(r, g, b)
            event_payload = {
                "game": GAME_NAME,
                "event": "SYNC_RGB",
                "data": {"value": 100}
            }
            self._post("/game_event", event_payload)
            return True
        except Exception as e:
            print(f"[!] Failed to set SteelSeries RGB: {e}")
            return False

    def sync_theme(self, theme_name: str) -> bool:
        """Syncs mouse RGB with the signature color of a theme preset."""
        color = THEME_RGB_MAP.get(theme_name.lower())
        if color:
            return self.set_color(color[0], color[1], color[2])
        return False

    def _heartbeat_loop(self):
        """Keeps GameSense game active with periodic keepalive."""
        while self.running:
            time.sleep(6.0)
            try:
                self._post("/game_heartbeat", {"game": GAME_NAME})
            except Exception:
                pass

    def _post(self, endpoint: str, payload: dict) -> dict:
        """Helper to send JSON POST request to GameSense."""
        url = f"{self.address}{endpoint}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else {}

    def stop(self):
        """Stops heartbeat and returns mouse to default profile."""
        self.running = False
        if self.connected:
            try:
                self._post("/remove_game", {"game": GAME_NAME})
            except Exception:
                pass
            self.connected = False
            print("[+] SteelSeries GameSense disconnected.")
