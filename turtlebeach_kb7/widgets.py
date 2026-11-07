"""
Turtle Beach Command Series KB7 - Widget Catalog and Template Engine.

Defines all built-in touch display widgets, App IDs, tile dimensions,
telemetry capabilities, and predefined layout templates.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class WidgetDefinition:
    """Definition of an individual touchscreen widget/application."""
    app_id: int
    name: str
    category: str
    tile_w: int
    tile_h: int
    runtime_update: bool
    suffix: str = ""
    description: str = ""


# Standard Widget App IDs
APP_NONE                = 0

# Virtual Keys (App IDs 1..23)
APP_KEY_0               = 1   # 2x1
APP_KEY_1               = 2
APP_KEY_2               = 3
APP_KEY_3               = 4
APP_KEY_4               = 5
APP_KEY_5               = 6
APP_KEY_6               = 7
APP_KEY_7               = 8
APP_KEY_8               = 9
APP_KEY_9               = 10
APP_KEY_DOT             = 11
APP_KEY_PRINT           = 12
APP_KEY_SCROLL_LOCK     = 13
APP_KEY_BREAK           = 14
APP_KEY_INSERT          = 15
APP_KEY_HOME            = 16
APP_KEY_END             = 17
APP_KEY_DELETE          = 18
APP_KEY_PAGE_UP         = 19
APP_KEY_PAGE_DOWN       = 20
APP_KEY_PLUS            = 21
APP_KEY_MINUS           = 22
APP_KEY_NUM_LOCK        = 23

# System & Media (App IDs 25..57)
APP_SPEAKER_MUTE        = 25
APP_SCREENSHOT          = 26
APP_GAMEBAR_SCREENSHOT  = 27
APP_GAMEBAR             = 28
APP_LOCK_PC             = 29
APP_SHUTDOWN            = 30
APP_EMOJI               = 31
APP_COPY                = 32
APP_PASTE               = 33
APP_LAUNCH_BROWSER      = 34
APP_BROWSER_BACK        = 35
APP_BROWSER_FORWARD     = 36
APP_CALCULATOR          = 37
APP_UNDO                = 38
APP_REDO                = 39
APP_CUT                 = 41
APP_MEDIA_CONTROLS_3X1  = 42  # 3x1
APP_SYS_MEDIA_CONTROLS  = 43  # 3x1
APP_RGB_BRIGHTNESS      = 44  # 3x1
APP_SCREEN_BRIGHTNESS   = 45  # 3x1
APP_REACTAP_SETTING     = 46
APP_LED_ADJUST_SETTING  = 49
APP_SCREEN_TIMEOUT      = 50
APP_SHUFFLE             = 51
APP_REPEAT              = 52
APP_BACK_TRACK          = 53
APP_STOP                = 54
APP_NEXT_TRACK          = 55
APP_PLAY_PAUSE          = 56
APP_VOLUME_MUTE         = 57

# Swarm II & Performance (App IDs 1000..1030)
APP_HOT_KEYS            = 1000
APP_REMAP_KEYS          = 1001
APP_OPEN_WEBSITE        = 1002
APP_OPEN_APP            = 1003
APP_LAUNCH_FILE         = 1004
APP_LAUNCH_FOLDER       = 1005
APP_CPU_USAGE           = 1006  # Runtime telemetry (%)
APP_GPU_USAGE           = 1007  # Runtime telemetry (%)
APP_CPU_TEMP            = 1008  # Runtime telemetry (°C)
APP_GPU_TEMP            = 1009  # Runtime telemetry (°C)
APP_RAM_USAGE           = 1010  # Runtime telemetry (%)
APP_DPI_UP              = 1011
APP_DPI_DOWN            = 1012
APP_RECORD_LAST_30S     = 1013
APP_MOUSE_BATTERY       = 1014  # Runtime telemetry (%)
APP_HEADSET_BATTERY     = 1016  # Runtime telemetry (%)
APP_LAUNCH_WORD         = 1018
APP_LAUNCH_EXCEL        = 1019
APP_TAI_MUTE_MIC        = 1021
APP_KEYBOARD_POLLING    = 1022
APP_MEDIA_SLIDER        = 1025  # 3x1
APP_MEDIA_SCRUB_BAR     = 1026  # 3x1
APP_MEDIA_CYCLE         = 1027
APP_MACRO               = 1028
APP_COUNTDOWN_TIMER     = 1030  # Runtime telemetry

# Third-Party Integrations (App IDs 3000..3600)
APP_DISCORD_VOICE       = 3002
APP_DISCORD_MUTE_MIC    = 3003
APP_DISCORD_MUTE_AUDIO  = 3004
APP_DISCORD_PTT         = 3005
APP_DISCORD_CHANNELS    = 3008

APP_CS2_PLAYED          = 3100
APP_CS2_ROUNDS_WON      = 3101
APP_CS2_ROUNDS_LOST     = 3102
APP_CS2_HEADSHOT        = 3103
APP_CS2_HEALTH          = 3104
APP_CS2_ARMOR           = 3105
APP_CS2_EQUIPPED        = 3106
APP_CS2_KDA             = 3107
APP_CS2_WEAPONS         = 3108
APP_CS2_AMMO            = 3109

APP_OBS_STREAM          = 3401
APP_OBS_RECORD          = 3402
APP_OBS_PAUSE           = 3403
APP_OBS_SCENE           = 3404
APP_OBS_PROFILE         = 3405
APP_OBS_STUDIO_MODE     = 3406
APP_OBS_SCREENSHOT      = 3407


# Complete Catalog Map
WIDGET_CATALOG: Dict[int, WidgetDefinition] = {
    APP_NONE: WidgetDefinition(0, "Empty Slot", "None", 1, 1, False),
    APP_KEY_0: WidgetDefinition(1, "Numpad 0", "Screen Keys", 2, 1, False),
    APP_KEY_1: WidgetDefinition(2, "Numpad 1", "Screen Keys", 1, 1, False),
    APP_KEY_2: WidgetDefinition(3, "Numpad 2", "Screen Keys", 1, 1, False),
    APP_KEY_3: WidgetDefinition(4, "Numpad 3", "Screen Keys", 1, 1, False),
    APP_KEY_4: WidgetDefinition(5, "Numpad 4", "Screen Keys", 1, 1, False),
    APP_KEY_5: WidgetDefinition(6, "Numpad 5", "Screen Keys", 1, 1, False),
    APP_KEY_6: WidgetDefinition(7, "Numpad 6", "Screen Keys", 1, 1, False),
    APP_KEY_7: WidgetDefinition(8, "Numpad 7", "Screen Keys", 1, 1, False),
    APP_KEY_8: WidgetDefinition(9, "Numpad 8", "Screen Keys", 1, 1, False),
    APP_KEY_9: WidgetDefinition(10, "Numpad 9", "Screen Keys", 1, 1, False),
    APP_KEY_DOT: WidgetDefinition(11, "Numpad .", "Screen Keys", 1, 1, False),
    APP_KEY_PRINT: WidgetDefinition(12, "Print Screen", "Screen Keys", 1, 1, False),
    APP_KEY_SCROLL_LOCK: WidgetDefinition(13, "Scroll Lock", "Screen Keys", 1, 1, False),
    APP_KEY_BREAK: WidgetDefinition(14, "Pause/Break", "Screen Keys", 1, 1, False),
    APP_KEY_INSERT: WidgetDefinition(15, "Insert", "Screen Keys", 1, 1, False),
    APP_KEY_HOME: WidgetDefinition(16, "Home", "Screen Keys", 1, 1, False),
    APP_KEY_END: WidgetDefinition(17, "End", "Screen Keys", 1, 1, False),
    APP_KEY_DELETE: WidgetDefinition(18, "Delete", "Screen Keys", 1, 1, False),
    APP_KEY_PAGE_UP: WidgetDefinition(19, "Page Up", "Screen Keys", 1, 1, False),
    APP_KEY_PAGE_DOWN: WidgetDefinition(20, "Page Down", "Screen Keys", 1, 1, False),
    APP_KEY_PLUS: WidgetDefinition(21, "Numpad +", "Screen Keys", 1, 1, False),
    APP_KEY_MINUS: WidgetDefinition(22, "Numpad -", "Screen Keys", 1, 1, False),
    APP_KEY_NUM_LOCK: WidgetDefinition(23, "Num Lock", "Screen Keys", 1, 1, False),

    APP_SPEAKER_MUTE: WidgetDefinition(25, "Speaker Mute", "Audio", 1, 1, True),
    APP_SCREENSHOT: WidgetDefinition(26, "Screen Shot", "Shortcuts", 1, 1, False),
    APP_GAMEBAR_SCREENSHOT: WidgetDefinition(27, "GameBar ScreenShot", "Windows", 1, 1, False),
    APP_GAMEBAR: WidgetDefinition(28, "Xbox Game Bar", "Windows", 1, 1, False),
    APP_LOCK_PC: WidgetDefinition(29, "Lock PC", "Windows", 1, 1, False),
    APP_SHUTDOWN: WidgetDefinition(30, "Shutdown", "Windows", 1, 1, False),
    APP_EMOJI: WidgetDefinition(31, "Emoji Picker", "Shortcuts", 1, 1, False),
    APP_COPY: WidgetDefinition(32, "Copy", "Shortcuts", 1, 1, False),
    APP_PASTE: WidgetDefinition(33, "Paste", "Shortcuts", 1, 1, False),
    APP_LAUNCH_BROWSER: WidgetDefinition(34, "Launch Browser", "Shortcuts", 1, 1, False),
    APP_BROWSER_BACK: WidgetDefinition(35, "Browser Back", "Shortcuts", 1, 1, False),
    APP_BROWSER_FORWARD: WidgetDefinition(36, "Browser Forward", "Shortcuts", 1, 1, False),
    APP_CALCULATOR: WidgetDefinition(37, "Calculator", "Shortcuts", 1, 1, False),
    APP_UNDO: WidgetDefinition(38, "Undo", "Shortcuts", 1, 1, False),
    APP_REDO: WidgetDefinition(39, "Redo", "Shortcuts", 1, 1, False),
    APP_CUT: WidgetDefinition(41, "Cut", "Shortcuts", 1, 1, False),

    APP_MEDIA_CONTROLS_3X1: WidgetDefinition(42, "Media Controls", "Multimedia", 3, 1, False),
    APP_RGB_BRIGHTNESS: WidgetDefinition(44, "Keyboard RGB Brightness", "Hardware", 3, 1, False),
    APP_SCREEN_BRIGHTNESS: WidgetDefinition(45, "Screen Brightness", "Hardware", 3, 1, False),
    APP_REACTAP_SETTING: WidgetDefinition(46, "REACTAP Rapid Trigger", "Hardware", 1, 1, False),
    APP_SCREEN_TIMEOUT: WidgetDefinition(50, "Screen Sleep Timeout", "Hardware", 1, 1, False),

    APP_PLAY_PAUSE: WidgetDefinition(56, "Play / Pause", "Multimedia", 1, 1, False),
    APP_VOLUME_MUTE: WidgetDefinition(57, "Volume Mute", "Multimedia", 1, 1, False),

    APP_OPEN_WEBSITE: WidgetDefinition(1002, "Open Website", "Launchers", 1, 1, False),
    APP_OPEN_APP: WidgetDefinition(1003, "Open App", "Launchers", 1, 1, False),
    APP_LAUNCH_FILE: WidgetDefinition(1004, "Launch File", "Launchers", 1, 1, False),
    APP_LAUNCH_FOLDER: WidgetDefinition(1005, "Launch Folder", "Launchers", 1, 1, False),

    APP_CPU_USAGE: WidgetDefinition(1006, "CPU Load", "Telemetry", 1, 1, True, "%", "Real-time CPU utilization"),
    APP_GPU_USAGE: WidgetDefinition(1007, "GPU Load", "Telemetry", 1, 1, True, "%", "Real-time GPU utilization"),
    APP_CPU_TEMP: WidgetDefinition(1008, "CPU Temperature", "Telemetry", 1, 1, True, "°C", "CPU core package temperature"),
    APP_GPU_TEMP: WidgetDefinition(1009, "GPU Temperature", "Telemetry", 1, 1, True, "°C", "GPU edge/die temperature"),
    APP_RAM_USAGE: WidgetDefinition(1010, "RAM Usage", "Telemetry", 1, 1, True, "%", "Real-time memory allocation percentage"),

    APP_DPI_UP: WidgetDefinition(1011, "Mouse DPI +", "Device Control", 1, 1, False),
    APP_DPI_DOWN: WidgetDefinition(1012, "Mouse DPI -", "Device Control", 1, 1, False),
    APP_RECORD_LAST_30S: WidgetDefinition(1013, "Record Last 30s", "Gaming", 1, 1, False),
    APP_MOUSE_BATTERY: WidgetDefinition(1014, "Mouse Battery", "Device Control", 1, 1, True, "%"),
    APP_HEADSET_BATTERY: WidgetDefinition(1016, "Headset Battery", "Device Control", 1, 1, True, "%"),

    APP_MEDIA_SLIDER: WidgetDefinition(1025, "Media Volume Slider", "Multimedia", 3, 1, False),
    APP_MEDIA_SCRUB_BAR: WidgetDefinition(1026, "Media Scrub Bar", "Multimedia", 3, 1, False),
    APP_MACRO: WidgetDefinition(1028, "Custom Macro", "Tools", 1, 1, False),
    APP_COUNTDOWN_TIMER: WidgetDefinition(1030, "Countdown Timer", "Tools", 1, 1, True),

    APP_DISCORD_MUTE_MIC: WidgetDefinition(3003, "Discord Mute Mic", "Discord", 1, 1, False),
    APP_DISCORD_MUTE_AUDIO: WidgetDefinition(3004, "Discord Mute Audio", "Discord", 1, 1, False),
    APP_DISCORD_PTT: WidgetDefinition(3005, "Discord Push-To-Talk", "Discord", 1, 1, False),

    APP_CS2_ROUNDS_WON: WidgetDefinition(3101, "CS2 Rounds Won", "CS2 HUD", 1, 1, True),
    APP_CS2_ROUNDS_LOST: WidgetDefinition(3102, "CS2 Rounds Lost", "CS2 HUD", 1, 1, True),
    APP_CS2_HEALTH: WidgetDefinition(3104, "CS2 Health", "CS2 HUD", 1, 1, True),
    APP_CS2_ARMOR: WidgetDefinition(3105, "CS2 Armor", "CS2 HUD", 1, 1, True),
    APP_CS2_KDA: WidgetDefinition(3107, "CS2 K/D/A", "CS2 HUD", 1, 1, True),
    APP_CS2_AMMO: WidgetDefinition(3109, "CS2 Ammo Count", "CS2 HUD", 1, 1, True),

    APP_OBS_STREAM: WidgetDefinition(3401, "OBS Stream Toggle", "OBS Studio", 1, 1, True),
    APP_OBS_RECORD: WidgetDefinition(3402, "OBS Record Toggle", "OBS Studio", 1, 1, True),
    APP_OBS_STUDIO_MODE: WidgetDefinition(3406, "OBS Studio Mode", "OBS Studio", 1, 1, True),
}


# Predefined Layout Templates (7 slots per page on KB7 hardware)
LAYOUT_TEMPLATES: Dict[str, List[int]] = {
    "dashboard": [
        APP_CPU_USAGE, APP_GPU_USAGE, APP_RAM_USAGE,
        APP_CALCULATOR, APP_SCREENSHOT, APP_PLAY_PAUSE, APP_SPEAKER_MUTE
    ],
    "factory": [
        APP_KEY_DOT, APP_KEY_PRINT, APP_KEY_SCROLL_LOCK,
        APP_KEY_BREAK, APP_KEY_INSERT, APP_KEY_DELETE, APP_KEY_END
    ],
    "telemetry": [
        APP_CPU_USAGE, APP_CPU_TEMP, APP_GPU_USAGE, APP_GPU_TEMP,
        APP_RAM_USAGE, APP_MOUSE_BATTERY, APP_HEADSET_BATTERY
    ],
    "productivity": [
        APP_COPY, APP_PASTE, APP_CALCULATOR,
        APP_SCREENSHOT, APP_LAUNCH_BROWSER, APP_LOCK_PC, APP_EMOJI
    ],
    "multimedia": [
        APP_BACK_TRACK, APP_PLAY_PAUSE, APP_NEXT_TRACK,
        APP_STOP, APP_VOLUME_MUTE, APP_SHUFFLE, APP_REPEAT
    ],
    "gaming": [
        APP_GAMEBAR, APP_RECORD_LAST_30S, APP_GAMEBAR_SCREENSHOT,
        APP_DISCORD_MUTE_MIC, APP_DISCORD_MUTE_AUDIO, APP_CPU_TEMP, APP_GPU_TEMP
    ],
    "obs": [
        APP_OBS_STREAM, APP_OBS_RECORD, APP_OBS_PAUSE,
        APP_OBS_STUDIO_MODE, APP_SCREENSHOT, APP_SPEAKER_MUTE, APP_PLAY_PAUSE
    ],
    "numpad": [
        APP_KEY_7, APP_KEY_8, APP_KEY_9,
        APP_KEY_4, APP_KEY_5, APP_KEY_6, APP_KEY_0
    ],
    "empty": [
        APP_NONE, APP_NONE, APP_NONE,
        APP_NONE, APP_NONE, APP_NONE, APP_NONE
    ]
}


def lookup_widget(app_id: int) -> WidgetDefinition:
    """Returns the WidgetDefinition for a given app_id or a generic fallback."""
    if app_id in WIDGET_CATALOG:
        return WIDGET_CATALOG[app_id]
    return WidgetDefinition(
        app_id=app_id,
        name=f"Custom App {app_id}",
        category="Custom",
        tile_w=1,
        tile_h=1,
        runtime_update=False
    )
