"""
Customizable RGB Lighting & Synchronized Effects Engine for Turtle Beach KB7 & SteelSeries Mouse.

Supports:
1. Dynamic Software-Synchronized Effects (driving all 7 planar RGB groups + per-key zones on the
   KB7 keyboard AND the SteelSeries GameSense mouse in real time with 3 customizable colors).
2. Native KB7 Hardware Effects (`Report 0x11`, 348 bytes: Static, ColorWave, Breathing, Heartbeat,
   Snake, Ripple, Fade FX, AIMO) with custom user colors (`color_flag = 0x0B`), speed (`1..11`),
   direction (`1..4`), and brightness (`0..100`).
"""

import json
import math
import os
import random
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

# Exact key r_offset mappings extracted from COMMAND_KB7.dll (0x4af800..0x4b0800)
# For any r_offset: Red = buf[10 + r_offset], Green = buf[26 + r_offset], Blue = buf[42 + r_offset]
ZONE_F_KEYS: List[int] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15]
ZONE_WASD: List[int] = [62, 107, 108, 109]          # W (62), A (107), S (108), D (109)
ZONE_ARROWS: List[int] = [198, 242, 243, 244]       # Up (198), Left (242), Down (243), Right (244)
ZONE_NUMROW: List[int] = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 63, 13]
ZONE_UNDERGLOW: List[int] = [288, 289, 290, 291, 292, 293, 294, 295, 296, 297]

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".kb7_lighting_config.json")

# Curated 3-Color Presets: (Name, Hex1, Hex2, Hex3)
COLOR_PALETTES: List[Tuple[str, str, str, str]] = [
    ("🟢 Matrix & Toxic", "#00FF66", "#39FF14", "#00E5FF"),
    ("🟣 Cyberpunk 2077", "#FF007F", "#00E5FF", "#FFE600"),
    ("🌅 Synthwave Sunset", "#FF0055", "#9B00FF", "#00F0FF"),
    ("🔥 Fire & Ice", "#FF2200", "#FF9900", "#00D2FF"),
    ("☢️ Biohazard Plasma", "#00FF88", "#AAFF00", "#0088FF"),
    ("👑 Royal Gold & Onyx", "#FFB800", "#FF5500", "#FFFFFF"),
    ("❄️ Arctic Glacier", "#00E5FF", "#0055FF", "#FFFFFF"),
    ("🩸 Crimson Vampyr", "#FF0022", "#8800FF", "#FF8800"),
    ("💎 Minecraft Diamond & Gold", "#00E5FF", "#FFB800", "#00FF66"),
]

# Complete catalog of customizable lighting effects
LIGHTING_EFFECTS: Dict[str, Dict[str, object]] = {
    "minecraft_reactive": {
        "name": "💎 Minecraft Reaktiv (Live HP Alert & Diamant Sync)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Fließender Diamant-Gold-Glow. Bei kritischem Leben (<30% HP) sofortiger roter Puls-Alarm!",
        "dynamic": True,
        "hw_mode": 7,
    },
    "cyber_wave": {
        "name": "🌊 3-Farb Cyber-Welle (Animierter Flow)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Fließende Welle aus Farbe 1, Farbe 2 und Farbe 3 über alle 7 Tastaturzonen & Maus.",
        "dynamic": True,
        "hw_mode": 7,
    },
    "static_gradient": {
        "name": "🎨 Multi-Zonen Farbverlauf (Statisch)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Sanfter 7-Zonen-Farbverlauf von Farbe 1 (Oben) über Farbe 2 (Mitte) bis Farbe 3 (Unten).",
        "dynamic": False,
        "hw_mode": 7,
    },
    "gaming_zones": {
        "name": "🎮 Taktische Gaming-Zonen (WASD + Pfeile + F-Keys)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Haupttasten in Farbe 1, WASD & F-Tasten in Farbe 2, Pfeiltasten & Underglow in Farbe 3.",
        "dynamic": False,
        "hw_mode": 7,
    },
    "neon_pulse": {
        "name": "💓 Dual/Tri-Color Neon-Atmen (Synchroner Puls)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Weiches synchrones Pulsieren zwischen Farbe 1, Farbe 2 und Farbe 3 auf Tastatur & Maus.",
        "dynamic": True,
        "hw_mode": 7,
    },
    "audio_vu": {
        "name": "🎵 Audio-Bass & Musik VU-Meter (Reaktiv)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Reagiert live auf Windows-Audio: Ruhe = Farbe 1, Mittel = Farbe 2, Bass-Peak = Farbe 3.",
        "dynamic": True,
        "hw_mode": 7,
    },
    "thermal_shift": {
        "name": "🌡️ System-Last Reaktor (CPU/RAM Reaktiv)",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Farbwechsel nach Systemlast: Kühl = Farbe 1, Mittel = Farbe 2, Volllast = Farbe 3.",
        "dynamic": True,
        "hw_mode": 7,
    },
    "plasma_storm": {
        "name": "⚡ Plasma-Gewitter & Energie-Blitze",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Atmosphärisches Glimmen in Farbe 1 mit dynamischen Blitzen in Farbe 2 und Farbe 3.",
        "dynamic": True,
        "hw_mode": 7,
    },
    "police_beacon": {
        "name": "🚨 Cyber-Sirene & Zonen-Strobe",
        "category": "Dynamisch (KB7 + Maus Sync)",
        "desc": "Rhythmischer Zonen-Wechsel zwischen Farbe 1, Farbe 2 und Farbe 3.",
        "dynamic": True,
        "hw_mode": 7,
    },
    "hw_static": {
        "name": "💡 Statisch Einfarbig (Hardware)",
        "category": "KB7 Hardware-Modus",
        "desc": "Komplette Tastatur und Maus dauerhaft in Farbe 1 beleuchtet.",
        "dynamic": False,
        "hw_mode": 7,
    },
    "hw_colorwave": {
        "name": "🌈 KB7 Hardware-Farbwelle (Custom Farben)",
        "category": "KB7 Hardware-Modus",
        "desc": "Native KB7 MCU-Wellenanimation mit deinen 3 benutzerdefinierten Farben.",
        "dynamic": False,
        "hw_mode": 1,
    },
    "hw_breathing": {
        "name": "🫁 KB7 Hardware-Atmen (Custom Farben)",
        "category": "KB7 Hardware-Modus",
        "desc": "Natives KB7 MCU-Atmen mit deinen 3 benutzerdefinierten Zonenfarben.",
        "dynamic": False,
        "hw_mode": 6,
    },
    "hw_heartbeat": {
        "name": "❤️ KB7 Hardware-Herzschlag (Custom Farben)",
        "category": "KB7 Hardware-Modus",
        "desc": "Nativer KB7 Herzschlag-Effekt in deinen 3 Wunschfarben.",
        "dynamic": False,
        "hw_mode": 10,
    },
    "hw_ripple": {
        "name": "💥 KB7 Hardware-Ripple (Explosion bei Tastendruck)",
        "category": "KB7 Hardware-Modus",
        "desc": "Löst bei jedem Tastendruck eine Lichtwelle in deinen Wunschfarben aus.",
        "dynamic": False,
        "hw_mode": 18,
    },
    "hw_fade": {
        "name": "✨ KB7 Hardware-Fade FX (Nachleuchten bei Tastendruck)",
        "category": "KB7 Hardware-Modus",
        "desc": "Tasten leuchten beim Tippen in deinen Wunschfarben auf und blenden sanft aus.",
        "dynamic": False,
        "hw_mode": 17,
    },
    "hw_snake": {
        "name": "🐍 KB7 Hardware-Snake (Schlange)",
        "category": "KB7 Hardware-Modus",
        "desc": "Native Schlangen-Animation über die Tastaturmatrix in deinen Wunschfarben.",
        "dynamic": False,
        "hw_mode": 8,
    },
    "hw_aimo": {
        "name": "🧠 KB7 Hardware-AIMO (Intelligent Fluid)",
        "category": "KB7 Hardware-Modus",
        "desc": "Organische reaktive AIMO-Beleuchtung direkt auf dem Keyboard-Prozessor.",
        "dynamic": False,
        "hw_mode": 9,
    },
}


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert '#RRGGBB' string to (R, G, B) tuple in 0..255."""
    s = str(hex_str).strip().lstrip("#")
    if len(s) != 6:
        return (0, 255, 102)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return (0, 255, 102)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert (R, G, B) tuple to '#RRGGBB' uppercase string."""
    r = max(0, min(255, int(rgb[0])))
    g = max(0, min(255, int(rgb[1])))
    b = max(0, min(255, int(rgb[2])))
    return f"#{r:02X}{g:02X}{b:02X}"


def lerp_rgb(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Linearly interpolate between two RGB colors for t in 0.0 .. 1.0."""
    t = max(0.0, min(1.0, float(t)))
    return (
        int(round(c1[0] + (c2[0] - c1[0]) * t)),
        int(round(c1[1] + (c2[1] - c1[1]) * t)),
        int(round(c1[2] + (c2[2] - c1[2]) * t)),
    )


def sample_3color_gradient(
    c1: Tuple[int, int, int],
    c2: Tuple[int, int, int],
    c3: Tuple[int, int, int],
    t: float,
) -> Tuple[int, int, int]:
    """Sample a 3-color gradient (c1 -> c2 -> c3) at position t in 0.0 .. 1.0."""
    t = max(0.0, min(1.0, float(t)))
    if t <= 0.5:
        return lerp_rgb(c1, c2, t * 2.0)
    return lerp_rgb(c2, c3, (t - 0.5) * 2.0)


def sample_3color_cycle(
    c1: Tuple[int, int, int],
    c2: Tuple[int, int, int],
    c3: Tuple[int, int, int],
    phase: float,
) -> Tuple[int, int, int]:
    """Sample a seamless closed loop (c1 -> c2 -> c3 -> c1) for phase in 0.0 .. 1.0."""
    p = phase % 1.0
    if p < 1.0 / 3.0:
        return lerp_rgb(c1, c2, p * 3.0)
    elif p < 2.0 / 3.0:
        return lerp_rgb(c2, c3, (p - 1.0 / 3.0) * 3.0)
    else:
        return lerp_rgb(c3, c1, (p - 2.0 / 3.0) * 3.0)


class LightingEngine:
    """
    Manages customizable RGB lighting effects across the KB7 keyboard (7 planar RGB groups + per-key zones)
    and SteelSeries GameSense mouse.
    """

    def __init__(self, hw_apply_callback: Optional[Callable] = None, steelseries=None):
        self.hw_apply_callback = hw_apply_callback
        self.steelseries = steelseries

        # User-customizable parameters
        self.effect_id: str = "cyber_wave"
        self.color1_hex: str = "#00FF66"  # Primary / Main keys
        self.color2_hex: str = "#00E5FF"  # Secondary / WASD / Mid gradient
        self.color3_hex: str = "#FF007F"  # Accent / Arrows / Peak
        self.speed: int = 6               # 1 .. 11
        self.brightness: int = 100        # 0 .. 100
        self.direction: int = 1           # 1 .. 4
        self.rainbow_override: bool = False
        self.kb_enabled: bool = True
        self.mouse_sync_enabled: bool = True

        # Live preview state (7 keyboard groups + mouse RGB + special zones)
        self.current_groups: List[Tuple[int, int, int]] = [(0, 255, 102)] * 7
        self.current_mouse_rgb: Tuple[int, int, int] = (0, 255, 102)
        self.current_key_offsets: Dict[int, Tuple[int, int, int]] = {}

        # Animation thread state
        self._running = False
        self._anim_thread: Optional[threading.Thread] = None
        self._phase: float = 0.0
        self._ui_preview_callback: Optional[Callable] = None
        self._audio_level: float = 0.25
        self._last_mouse_sent: Tuple[int, int, int] = (-1, -1, -1)

        self.load_config()

    def load_config(self) -> None:
        if not os.path.exists(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("effect_id") in LIGHTING_EFFECTS:
                self.effect_id = data["effect_id"]
            self.color1_hex = str(data.get("color1_hex", self.color1_hex))
            self.color2_hex = str(data.get("color2_hex", self.color2_hex))
            self.color3_hex = str(data.get("color3_hex", self.color3_hex))
            self.speed = max(1, min(11, int(data.get("speed", self.speed))))
            self.brightness = max(0, min(100, int(data.get("brightness", self.brightness))))
            self.direction = max(1, min(4, int(data.get("direction", self.direction))))
            self.rainbow_override = bool(data.get("rainbow_override", False))
            self.kb_enabled = bool(data.get("kb_enabled", True))
            self.mouse_sync_enabled = bool(data.get("mouse_sync_enabled", True))
        except Exception:
            pass

    def save_config(self) -> None:
        data = {
            "effect_id": self.effect_id,
            "color1_hex": self.color1_hex,
            "color2_hex": self.color2_hex,
            "color3_hex": self.color3_hex,
            "speed": self.speed,
            "brightness": self.brightness,
            "direction": self.direction,
            "rainbow_override": self.rainbow_override,
            "kb_enabled": self.kb_enabled,
            "mouse_sync_enabled": self.mouse_sync_enabled,
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def set_preview_callback(self, cb: Optional[Callable]) -> None:
        self._ui_preview_callback = cb

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._anim_thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._anim_thread.start()

    def stop(self) -> None:
        self._running = False

    def compute_frame(self, phase: float) -> Tuple[int, List[Tuple[int, int, int]], Dict[int, Tuple[int, int, int]], Tuple[int, int, int]]:
        """
        Compute `(hw_mode, group_colors_7, key_offsets_rgb, mouse_rgb)` for the active effect at `phase`.
        """
        c1 = hex_to_rgb(self.color1_hex)
        c2 = hex_to_rgb(self.color2_hex)
        c3 = hex_to_rgb(self.color3_hex)

        meta = LIGHTING_EFFECTS.get(self.effect_id, LIGHTING_EFFECTS["cyber_wave"])
        hw_mode = int(meta.get("hw_mode", 7))
        key_offsets: Dict[int, Tuple[int, int, int]] = {}

        if self.effect_id == "minecraft_reactive":
            # Minecraft ATM10 Dynamic Reactive Lighting
            # Normal: Diamond Cyan (#00E5FF) + Obsidian Gold (#FFB800) + XP Green (#00FF66)
            # Critical Health (<30% HP): Fast Crimson Red Heartbeat Pulse!
            from .minecraft import load_minecraft_stats
            mc_stats = load_minecraft_stats()
            is_low = mc_stats.is_low_health if mc_stats else False
            if is_low:
                # Fast urgent red pulse (frequency 3Hz)
                pulse = (math.sin(phase * 6.0 * math.pi) + 1.0) * 0.5
                red_alert = (int(120 + 135 * pulse), 0, int(15 * pulse))
                groups = [red_alert] * 7
                for off in ZONE_WASD:
                    key_offsets[off] = (255, 255, 255)
                mouse_rgb = red_alert
            else:
                # Flowing Diamond Cyan to Gold with XP green WASD
                groups = [sample_3color_cycle(c1, c2, c3, phase + (i / 7.0)) for i in range(7)]
                for off in ZONE_WASD:
                    key_offsets[off] = c3
                for off in ZONE_UNDERGLOW:
                    key_offsets[off] = c2
                mouse_rgb = c1

        elif self.effect_id == "static_gradient":
            groups = [sample_3color_gradient(c1, c2, c3, i / 6.0) for i in range(7)]
            mouse_rgb = c2

        elif self.effect_id == "gaming_zones":
            # Main keyboard rows in Color 1, Underglow in Color 3
            groups = [c1, c1, c1, c1, c1, c1, c3]
            for off in ZONE_F_KEYS:
                key_offsets[off] = c2
            for off in ZONE_WASD:
                key_offsets[off] = c2
            for off in ZONE_ARROWS:
                key_offsets[off] = c3
            for off in ZONE_UNDERGLOW:
                key_offsets[off] = c3
            mouse_rgb = c2

        elif self.effect_id == "cyber_wave":
            dir_sign = -1.0 if self.direction in (2, 4) else 1.0
            groups = [
                sample_3color_cycle(c1, c2, c3, phase * dir_sign + (i / 7.0))
                for i in range(7)
            ]
            mouse_rgb = sample_3color_cycle(c1, c2, c3, phase)

        elif self.effect_id == "neon_pulse":
            wave = (math.sin(phase * 2.0 * math.pi) + 1.0) * 0.5
            main_col = sample_3color_gradient(c1, c2, c3, wave)
            accent_col = sample_3color_gradient(c3, c2, c1, wave)
            groups = [
                lerp_rgb(main_col, accent_col, i / 6.0)
                for i in range(7)
            ]
            for off in ZONE_WASD:
                key_offsets[off] = accent_col
            mouse_rgb = main_col

        elif self.effect_id == "audio_vu":
            lvl = max(0.05, min(1.0, self._audio_level))
            active_zones = int(round(lvl * 7))
            groups = []
            for i in range(7):
                zone_pos = i / 6.0
                if i < active_zones:
                    groups.append(sample_3color_gradient(c1, c2, c3, zone_pos))
                else:
                    dim_c1 = (c1[0] // 5, c1[1] // 5, c1[2] // 5)
                    groups.append(dim_c1)
            mouse_rgb = sample_3color_gradient(c1, c2, c3, lvl)

        elif self.effect_id == "thermal_shift":
            load = self._sample_system_load()
            col = sample_3color_gradient(c1, c2, c3, load)
            groups = [col] * 7
            for off in ZONE_WASD:
                key_offsets[off] = c3 if load > 0.6 else c2
            mouse_rgb = col

        elif self.effect_id == "plasma_storm":
            groups = [lerp_rgb(c1, c2, 0.25 * (math.sin(phase * 2 * math.pi + i) + 1.0)) for i in range(7)]
            flash_idx = int((phase * 17) % 7)
            groups[flash_idx] = c3
            for off in ZONE_WASD:
                key_offsets[off] = c2
            mouse_rgb = c3 if (int(phase * 10) % 4 == 0) else c1

        elif self.effect_id == "police_beacon":
            half = int(phase * 2.0) % 2 == 0
            groups = [
                (c1 if (i < 3) == half else c3)
                for i in range(7)
            ]
            groups[3] = c2
            mouse_rgb = c1 if half else c3

        elif self.effect_id == "hw_static":
            groups = [c1] * 7
            mouse_rgb = c1

        else:
            # Native KB7 hardware modes (ColorWave, Breathing, Heartbeat, Ripple, Fade, Snake, AIMO)
            groups = [sample_3color_gradient(c1, c2, c3, i / 6.0) for i in range(7)]
            for off in ZONE_WASD:
                key_offsets[off] = c2
            for off in ZONE_ARROWS:
                key_offsets[off] = c3
            mouse_rgb = c1

        return hw_mode, groups, key_offsets, mouse_rgb

    def _sample_system_load(self) -> float:
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            base = (stat.dwMemoryLoad / 100.0)
            jitter = 0.15 * math.sin(time.time() * 1.5)
            return max(0.0, min(1.0, base + jitter))
        except Exception:
            return 0.4

    def update_audio_level(self, level_0_to_1: float) -> None:
        self._audio_level = max(0.0, min(1.0, float(level_0_to_1)))

    def apply_now(self) -> bool:
        """Immediately compute and send the current lighting state to KB7 hardware & SteelSeries mouse."""
        hw_mode, groups, key_offsets, mouse_rgb = self.compute_frame(self._phase)
        self.current_groups = groups
        self.current_key_offsets = key_offsets
        self.current_mouse_rgb = mouse_rgb

        if self._ui_preview_callback:
            try:
                self._ui_preview_callback(groups, key_offsets, mouse_rgb)
            except Exception:
                pass

        color_flag = 0x00 if self.rainbow_override else 0x0B
        ok = True

        if self.kb_enabled and self.hw_apply_callback:
            try:
                ok = bool(
                    self.hw_apply_callback(
                        mode=hw_mode,
                        speed=self.speed,
                        brightness=self.brightness,
                        color_flag=color_flag,
                        direction=self.direction,
                        group_colors=groups,
                        key_offsets_rgb=key_offsets,
                    )
                )
            except Exception as e:
                print(f"[!] KB7 lighting apply error: {e}")
                ok = False

        if self.mouse_sync_enabled and self.steelseries:
            try:
                scale = self.brightness / 100.0
                mr = int(mouse_rgb[0] * scale)
                mg = int(mouse_rgb[1] * scale)
                mb = int(mouse_rgb[2] * scale)
                prev_r, prev_g, prev_b = self._last_mouse_sent
                if abs(mr - prev_r) + abs(mg - prev_g) + abs(mb - prev_b) >= 6:
                    self._last_mouse_sent = (mr, mg, mb)
                    self.steelseries.set_color(mr, mg, mb)
            except Exception:
                pass

        return ok

    def _animation_loop(self) -> None:
        """Background thread that animates dynamic software-synced effects without saturating USB HID."""
        time.sleep(0.6)
        self.apply_now()
        while self._running:
            meta = LIGHTING_EFFECTS.get(self.effect_id, {})
            if meta.get("dynamic", False):
                step = 0.025 + (self.speed / 11.0) * 0.085
                self._phase = (self._phase + step) % 1.0

                if self.effect_id == "audio_vu":
                    beat = 0.25 + 0.70 * abs(math.sin(time.time() * (2.2 + self.speed * 0.35)))
                    self._audio_level = beat

                self.apply_now()
                time.sleep(0.42)
            else:
                time.sleep(0.50)
