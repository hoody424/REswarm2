"""
Complete catalog of widgets and default templates for the Turtle Beach Command Series KB7.

Extracted from:
- COMMAND_KB7.dll (0x002AE170..0x002B044F: app_id <-> (w_type, w_id) table)
- Command_KB7_Profile_Mgr.dat (CommandKB7LCD 0x25 & CommandKB7ScreenKeys 0x29)
- kb7_default_browse_templates.ini
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class WidgetInfo:
    app_id: int
    name: str
    category: str
    span: Tuple[int, int] = (1, 1)  # (cols, rows) in the 4x3 page grid
    runtime_update: bool = False


# Exact firmware (w_type, w_id) mapping extracted from COMMAND_KB7.dll (0x002AE170)
APP_ID_TO_FIRMWARE: Dict[int, Tuple[int, int]] = {
    0: (0, 0),
    # Numpad & 6-Island Keys (w_type = 3, w_id = 0..22)
    1: (3, 0),
    2: (3, 1),
    3: (3, 2),
    4: (3, 3),
    5: (3, 4),
    6: (3, 5),
    7: (3, 6),
    8: (3, 7),
    9: (3, 8),
    10: (3, 9),
    11: (3, 10),
    12: (3, 11),
    13: (3, 12),
    14: (3, 13),
    15: (3, 14),
    16: (3, 15),
    17: (3, 18),  # End (matched to Command_KB7_Profile_Mgr.dat Slot 8)
    18: (3, 17),  # Delete (matched to Command_KB7_Profile_Mgr.dat Slot 9)
    19: (3, 16),  # Page Up (matched to Command_KB7_Profile_Mgr.dat Slot 10)
    20: (3, 19),  # Page Down (matched to Command_KB7_Profile_Mgr.dat Slot 11)
    21: (3, 20),
    22: (3, 21),
    23: (3, 22),
    # Action / Shortcut / Media Tiles
    25: (72, 0),   # Emoji
    26: (62, 0),   # Screen Shot
    27: (23, 0),   # Task Manager
    28: (21, 0),   # Lock PC
    29: (59, 0),   # Speaker / Mute Volume
    30: (60, 0),   # Mic Mute
    31: (24, 0),   # Calculator / Shortcut 1
    32: (25, 0),   # Explorer / Shortcut 2
    33: (26, 0),   # Browser / Shortcut 3
    34: (27, 0),   # Mail / Shortcut 4
    35: (28, 0),   # Media Play/Pause / Shortcut 5
    36: (29, 0),   # Media Next / Shortcut 6
    37: (30, 0),   # Media Prev / Shortcut 7
    38: (31, 0),   # Media Stop / Shortcut 8
    39: (32, 0),   # Settings / Shortcut 9
    40: (1, 2),    # Macro Slot
    41: (71, 0),   # Quick Action
    43: (20, 0),   # Custom Function
    # System Telemetry & Clocks
    1000: (5, 1),  # CPU Usage
    1001: (5, 0),  # System Overview
    1002: (5, 5),  # GPU Usage
    1003: (5, 6),  # RAM Usage
    1004: (5, 3),  # CPU Temperature
    1005: (5, 4),  # GPU Temperature
    1006: (58, 0), # CPU Temp Mini Tile
    1007: (56, 0), # GPU Load Mini Tile
    1008: (57, 0), # CPU Load Mini Tile
    1009: (55, 0), # GPU Temp Mini Tile
    1010: (65, 0), # RAM Load Mini Tile
    1011: (63, 0), # Network Upload Mini Tile
    1012: (64, 0), # Network Download Mini Tile
    1013: (22, 0), # Network Speed
    1014: (26, 0), # Analog Clock (Page 2 Slot 5 in factory profile)
    1015: (69, 0), # Digital Clock
    1016: (27, 0), # Weather / Date (Page 2 Slot 6 in factory profile)
    1024: (69, 0), # Digital Clock (Large)
    1025: (52, 0), # Media Player (4x2)
    1028: (5, 2),  # Network Monitor
    1030: (70, 0), # Volume Mixer
    # Keyboard / RGB Controls
    3000: (54, 0), # Profile Switch
    3001: (54, 1), # Brightness Control
    3002: (54, 1), # Lighting Effect
    3003: (54, 2), # Volume Wheel Mode
    3004: (54, 3), # Actuation Point
    3005: (54, 4), # Rapid Trigger
    3006: (54, 5), # Game Mode
    3007: (54, 6), # Easy-Shift[+]
    3008: (54, 8), # SOCD Mode
    # Timer / Stopwatch / Widgets
    3100: (61, 0),
    3101: (61, 1),
    3102: (61, 2),
    3104: (61, 3),
    3105: (61, 5),
    3106: (61, 7),
    3107: (61, 8),
    3109: (61, 10),
    3400: (75, 0),
    3401: (67, 0),
    3402: (67, 2),
    3403: (67, 1),
    3404: (67, 6),
    3405: (67, 4),
    3406: (67, 9),
    3407: (67, 7),
    3409: (67, 3),
    3410: (67, 5),
    3501: (68, 0),
    3502: (68, 1),
    3503: (68, 2),
    3600: (66, 0),
}

FIRMWARE_TO_APP_ID: Dict[Tuple[int, int], int] = {
    v: k for k, v in reversed(list(APP_ID_TO_FIRMWARE.items()))
}

# Report 0x29 (ScreenKeys) HID Usage ID & ASCII label for w_type == 3 keys
SCREEN_KEY_BINDINGS: Dict[int, Tuple[int, str]] = {
    1:  (0x62, "0"),
    2:  (0x59, "1"),
    3:  (0x5A, "2"),
    4:  (0x5B, "3"),
    5:  (0x5C, "4"),
    6:  (0x5D, "5"),
    7:  (0x5E, "6"),
    8:  (0x5F, "7"),
    9:  (0x60, "8"),
    10: (0x61, "9"),
    11: (0x63, "."),
    12: (0x46, "PRINT"),
    13: (0x47, "SCR LK"),
    14: (0x48, "BREAK"),
    15: (0x49, "INS"),
    16: (0x4A, "HOME"),
    17: (0x4D, "END"),
    18: (0x4C, "DEL"),
    19: (0x4B, "PGUP"),
    20: (0x4E, "PGDOWN"),
    21: (0x54, "/"),
    22: (0x55, "*"),
    23: (0x56, "-"),
}


WIDGET_CATALOG: Dict[int, WidgetInfo] = {
    0: WidgetInfo(0, "Empty Slot", "System", (1, 1)),

    # Numpad & Navigation Keys (IDs 1-23)
    1: WidgetInfo(1, "Numpad 0 (Wide)", "Numpad", (2, 1)),
    2: WidgetInfo(2, "Numpad 1", "Numpad", (1, 1)),
    3: WidgetInfo(3, "Numpad 2", "Numpad", (1, 1)),
    4: WidgetInfo(4, "Numpad 3", "Numpad", (1, 1)),
    5: WidgetInfo(5, "Numpad 4", "Numpad", (1, 1)),
    6: WidgetInfo(6, "Numpad 5", "Numpad", (1, 1)),
    7: WidgetInfo(7, "Numpad 6", "Numpad", (1, 1)),
    8: WidgetInfo(8, "Numpad 7", "Numpad", (1, 1)),
    9: WidgetInfo(9, "Numpad 8", "Numpad", (1, 1)),
    10: WidgetInfo(10, "Numpad 9", "Numpad", (1, 1)),
    11: WidgetInfo(11, "Numpad . (Decimal)", "Numpad", (1, 1)),
    12: WidgetInfo(12, "Print Screen", "6-Island Keys", (1, 1)),
    13: WidgetInfo(13, "Scroll Lock", "6-Island Keys", (1, 1)),
    14: WidgetInfo(14, "Pause / Break", "6-Island Keys", (1, 1)),
    15: WidgetInfo(15, "Insert", "6-Island Keys", (1, 1)),
    16: WidgetInfo(16, "Home", "6-Island Keys", (1, 1)),
    17: WidgetInfo(17, "End", "6-Island Keys", (1, 1)),
    18: WidgetInfo(18, "Delete", "6-Island Keys", (1, 1)),
    19: WidgetInfo(19, "Page Up", "6-Island Keys", (1, 1)),
    20: WidgetInfo(20, "Page Down", "6-Island Keys", (1, 1)),
    21: WidgetInfo(21, "Numpad /", "Numpad", (1, 1)),
    22: WidgetInfo(22, "Numpad *", "Numpad", (1, 1)),
    23: WidgetInfo(23, "Numpad -", "Numpad", (1, 1)),

    # Media & OS Shortcuts (IDs 25-39)
    29: WidgetInfo(29, "Speaker Mute (1x1)", "Media & OS", (1, 1)),
    26: WidgetInfo(26, "Screen Shot (1x1)", "Media & OS", (1, 1)),
    25: WidgetInfo(25, "Emoji Panel (1x1)", "Media & OS", (1, 1)),
    27: WidgetInfo(27, "Task Manager (1x1)", "Media & OS", (1, 1)),
    28: WidgetInfo(28, "Lock PC (1x1)", "Media & OS", (1, 1)),
    30: WidgetInfo(30, "Mic Mute (1x1)", "Media & OS", (1, 1)),
    31: WidgetInfo(31, "Calculator (1x1)", "Media & OS", (1, 1)),
    32: WidgetInfo(32, "File Explorer (1x1)", "Media & OS", (1, 1)),
    33: WidgetInfo(33, "Web Browser (1x1)", "Media & OS", (1, 1)),
    34: WidgetInfo(34, "Mail / App 4 (1x1)", "Media & OS", (1, 1)),
    35: WidgetInfo(35, "Media Play/Pause (1x1)", "Media & OS", (1, 1)),
    36: WidgetInfo(36, "Media Next (1x1)", "Media & OS", (1, 1)),
    37: WidgetInfo(37, "Media Prev (1x1)", "Media & OS", (1, 1)),
    38: WidgetInfo(38, "Media Stop (1x1)", "Media & OS", (1, 1)),
    39: WidgetInfo(39, "Settings (1x1)", "Media & OS", (1, 1)),

    # System Telemetry & Clocks (IDs 1000-1030)
    1000: WidgetInfo(1000, "CPU Usage (2x1 Large)", "Telemetry", (2, 1)),
    1002: WidgetInfo(1002, "GPU Usage (2x1 Large)", "Telemetry", (2, 1)),
    1003: WidgetInfo(1003, "RAM Usage (2x1 Large)", "Telemetry", (2, 1)),
    1006: WidgetInfo(1006, "CPU Temp (1x1 Mini)", "Telemetry", (1, 1)),
    1007: WidgetInfo(1007, "GPU Load (1x1 Mini)", "Telemetry", (1, 1)),
    1008: WidgetInfo(1008, "CPU Load (1x1 Mini)", "Telemetry", (1, 1)),
    1009: WidgetInfo(1009, "GPU Temp (1x1 Mini)", "Telemetry", (1, 1)),
    1010: WidgetInfo(1010, "RAM Load (1x1 Mini)", "Telemetry", (1, 1)),
    1011: WidgetInfo(1011, "Net Upload (1x1 Mini)", "Telemetry", (1, 1)),
    1012: WidgetInfo(1012, "Net Download (1x1 Mini)", "Telemetry", (1, 1)),
    1013: WidgetInfo(1013, "Network Speed (1x1)", "Telemetry", (1, 1)),
    1014: WidgetInfo(1014, "Analog Clock (1x1)", "Clock & Info", (1, 1)),
    1024: WidgetInfo(1024, "Digital Clock (2x1 Large)", "Clock & Info", (2, 1)),
    1016: WidgetInfo(1016, "Weather / Date (1x1)", "Clock & Info", (1, 1)),
    1025: WidgetInfo(1025, "Media Player (4x2 Large)", "Media & OS", (4, 2)),
    1030: WidgetInfo(1030, "Volume Mixer (1x1)", "Media & OS", (1, 1)),

    # Keyboard Controls (IDs 3000-3008)
    3002: WidgetInfo(3002, "RGB Lighting Effect", "Keyboard", (1, 1)),
    3003: WidgetInfo(3003, "Volume Wheel Mode", "Keyboard", (1, 1)),
    3004: WidgetInfo(3004, "Actuation Point", "Keyboard", (1, 1)),
    3005: WidgetInfo(3005, "Rapid Trigger", "Keyboard", (1, 1)),
    3008: WidgetInfo(3008, "SOCD Mode", "Keyboard", (1, 1)),
}


# Default 12-slot page templates from kb7_default_browse_templates.ini & Command_KB7_Profile_Mgr.dat
DEFAULT_TEMPLATES: Dict[str, List[int]] = {
    "Default 1 (Home / 6-Island - 12 Tiles)": [29, 26, 25, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    "Default 2 (PC Telemetry & Shortcuts)": [1006, 1008, 1007, 1009, 1010, 1014, 1016, 3003, 3004, 1013, 27, 28],
    "Numpad": [8, 9, 10, 5, 6, 7, 2, 3, 4, 1, 0, 11],
    "PC Status (Large Gauges)": [1000, 0, 1002, 0, 1003, 0, 1006, 1009, 1011, 1012, 27, 28],
    "Media & Audio": [29, 30, 1030, 26, 25, 31, 32, 33, 3002, 3003, 27, 28],
    "Clean Wallpaper (All Empty)": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
}

LAYOUT_TEMPLATES: Dict[str, List[int]] = {
    "factory":      [29, 26, 25, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    "streamdeck":   [35, 37, 36, 29, 30, 12, 13, 14, 15, 16, 26, 1030],
    "dashboard":    [1006, 1008, 1007, 1009, 1010, 1014, 1016, 3003, 3004, 1013, 27, 28],
    "telemetry":    [1006, 1008, 1007, 1009, 1010, 1011, 1012, 1013, 1014, 1016, 27, 28],
    "telemetry_2x1":[1000, 0, 1002, 0, 1003, 0, 1006, 1009, 1011, 1012, 1013, 1014],
    "productivity": [29, 26, 25, 31, 32, 33, 12, 16, 17, 18, 19, 20],
    "multimedia":   [35, 37, 36, 38, 29, 30, 1030, 26, 25, 33, 3002, 3003],
    "gaming":       [1006, 1007, 1008, 1009, 3004, 3005, 3008, 3002, 29, 30, 26, 27],
    "obs":          [35, 37, 36, 29, 30, 26, 12, 13, 14, 15, 1008, 1007],
    "numpad":       [8, 9, 10, 5, 6, 7, 2, 3, 4, 1, 0, 11],
    "empty":        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    **DEFAULT_TEMPLATES,
}


def lookup_widget(app_id: int) -> WidgetInfo:
    """Return WidgetInfo for `app_id`, falling back to a descriptive entry if unknown."""
    if app_id in WIDGET_CATALOG:
        return WIDGET_CATALOG[app_id]
    if (app_id, 0) in FIRMWARE_TO_APP_ID:
        mapped = FIRMWARE_TO_APP_ID[(app_id, 0)]
        if mapped in WIDGET_CATALOG:
            return WIDGET_CATALOG[mapped]
    return WidgetInfo(app_id, f"Widget #{app_id}", "Custom", (1, 1), False)
