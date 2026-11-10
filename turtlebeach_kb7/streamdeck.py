"""
Smart Stream Deck & Twitch/Browser Stream Companion Engine for the Turtle Beach Command Series KB7.

Implements all proposed Stream Companion & Display Streaming features:
1. Live Browser / Twitch / YouTube / OBS / Spotify Stream Detection (Win32 window scanner
   extracting platform, live status badge, streamer/video title, and window coordinates).
2. Two Display-Streaming Modes for the KB7 LCD:
   - Full-Screen Snapshot Stream (`480x800` Slot `0x00` with Live Stream Companion HUD overlay,
     manual 1-click or automatic interval loop every 10s/15s/30s).
   - Fast Mini-Tile Slideshow Stream (`142x148` Slot `0x40`, 63 KB -> ~0.9s per frame).
3. 12-Slot Compact `1x1` Hardware Stream Deck on Page 3 (`Report 0x25` + `Report 0x29` custom labels)
   with bidirectional KB7 Touchscreen execution (`0xFF02`).
"""

from dataclasses import dataclass, asdict
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import time
import webbrowser
from typing import Callable, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageGrab

from .image import LCD_WIDTH, LCD_HEIGHT, THUMB_WIDTH, THUMB_HEIGHT, scale_and_center_crop

STREAMDECK_CONFIG_PATH = Path.home() / ".kb7_streamdeck.json"


@dataclass
class StreamDeckTile:
    slot: int
    icon: str
    title: str
    subtitle: str
    color: str
    action_id: str
    hw_app_id: int          # KB7 Firmware widget app_id (1x1 small tile by default)
    hw_label: str = ""      # Up to 11 ASCII chars for Report 0x29 (when hw_app_id is 2..23)
    hid_code: int = 0x00    # Optional HID keycode in Report 0x29
    rgb_sync: Tuple[int, int, int] = (0, 229, 255)


@dataclass
class DetectedStreamWindow:
    hwnd: int
    title: str
    platform: str           # "TWITCH", "YOUTUBE", "OBS STUDIO", "SPOTIFY", "BROWSER", "SCREEN"
    clean_title: str
    badge_color: Tuple[int, int, int]
    rect: Tuple[int, int, int, int]


# Complete Catalog of Smart Stream Companion Actions executable from GUI or KB7 Touchscreen
STREAMDECK_ACTIONS: Dict[str, Dict[str, str]] = {
    "media_play_pause":    {"name": "⏯ Media/Stream: Play / Pause", "cat": "Stream & Media"},
    "media_prev":          {"name": "⏮ Media: Vorheriger Track / Zurück", "cat": "Stream & Media"},
    "media_next":          {"name": "⏭ Media: Nächster Track / Weiter", "cat": "Stream & Media"},
    "media_stop":          {"name": "⏹ Media: Stop", "cat": "Stream & Media"},
    "focus_stream":        {"name": "🎯 Stream: 1-Klick Fensterwechsel zum Stream", "cat": "Stream Companion"},
    "browser_fullscreen":  {"name": "⛶ Stream: Video Vollbild umschalten (F)", "cat": "Stream Companion"},
    "twitch_theater":      {"name": "🎭 Twitch: Theater-Modus (Alt+T)", "cat": "Stream Companion"},
    "stream_snapshot":     {"name": "📸 Display: Live-Stream-Snapshot auf KB7 senden", "cat": "Display-Stream"},
    "toggle_auto_stream":  {"name": "🔄 Display: Auto-Snapshot-Stream Start/Stop", "cat": "Display-Stream"},
    "audio_mute":          {"name": "🔇 Audio: Lautsprecher Mute/Unmute", "cat": "Audio"},
    "mic_mute":            {"name": "🎙 Audio: Mikrofon Mute/Unmute", "cat": "Audio"},
    "vol_up":              {"name": "🔊 Audio: Lautstärke +5%", "cat": "Audio"},
    "vol_down":            {"name": "🔉 Audio: Lautstärke -5%", "cat": "Audio"},
    "open_twitch":         {"name": "🟣 Stream: Twitch öffnen & LED-Sync", "cat": "Stream Companion"},
    "open_youtube":        {"name": "🔴 Stream: YouTube öffnen & LED-Sync", "cat": "Stream Companion"},
    "app_spotify":         {"name": "🟢 App: Spotify öffnen / Fokus", "cat": "Apps"},
    "app_discord":         {"name": "💬 App: Discord öffnen / Fokus", "cat": "Apps"},
    "hotkey_discord_mute": {"name": "🎙 Discord: Mic Mute (Ctrl+Shift+M)", "cat": "Discord"},
    "hotkey_discord_deaf": {"name": "🎧 Discord: Deafen (Ctrl+Shift+D)", "cat": "Discord"},
    "hotkey_clip":         {"name": "🎬 Clip: Instant Replay speichern (Alt+F10)", "cat": "Streaming"},
    "hotkey_record":       {"name": "⏺ Aufnahme: Game Bar Record (Win+Alt+R)", "cat": "Streaming"},
    "hotkey_obs_stream":   {"name": "📡 OBS: Stream Start/Stop (Ctrl+Shift+F10)", "cat": "OBS Studio"},
    "hotkey_obs_rec":      {"name": "🎥 OBS: Aufnahme Start/Stop (Ctrl+Shift+F11)", "cat": "OBS Studio"},
    "hotkey_scene1":       {"name": "🖥 OBS: Szene 1 - Main (Ctrl+Alt+F1)", "cat": "OBS Studio"},
    "hotkey_scene2":       {"name": "🎮 OBS: Szene 2 - Game (Ctrl+Alt+F2)", "cat": "OBS Studio"},
    "hotkey_scene3":       {"name": "☕ OBS: Szene 3 - BRB (Ctrl+Alt+F3)", "cat": "OBS Studio"},
    "hotkey_screenshot":   {"name": "✂ Screenshot: Snipping Tool (Win+Shift+S)", "cat": "System"},
    "hotkey_clipboard":    {"name": "📋 System: Zwischenablageverlauf (Win+V)", "cat": "System"},
    "show_desktop":        {"name": "🖥 System: Desktop anzeigen (Win+D)", "cat": "System"},
    "open_taskmgr":        {"name": "📊 System: Task-Manager öffnen", "cat": "System"},
    "open_calc":           {"name": "🧮 System: Taschenrechner öffnen", "cat": "System"},
    "open_explorer":       {"name": "📁 System: Datei-Explorer öffnen", "cat": "System"},
    "open_terminal":       {"name": "💻 System: Windows Terminal / PowerShell", "cat": "System"},
    "lock_pc":             {"name": "🔒 System: PC sperren (Win+L)", "cat": "System"},
    "switch_hw_page":      {"name": "📄 KB7: Display-Seite weiterschalten (1→2→3)", "cat": "Hardware"},
    "none":                {"name": "ℹ Nur Hardware-Kachel / Telemetrie", "cat": "Hardware"},
}


# Pre-built 12-Slot Profiles using compact 1x1 hardware tiles
STREAMDECK_PROFILES: Dict[str, List[StreamDeckTile]] = {
    "common_deck": [
        StreamDeckTile(0,  "⏯", "PLAY / PAUSE", "Universal Media",  "#00e575", "media_play_pause",    35,   "PLAY/PAUSE", 0x00, (0, 255, 117)),
        StreamDeckTile(1,  "⏭", "NEXT TRACK",  "Nächster Song",    "#00e5ff", "media_next",          36,   "NEXT TRACK", 0x00, (0, 229, 255)),
        StreamDeckTile(2,  "🎙", "MIC MUTE",     "Mikrofon Mute",    "#ff5252", "mic_mute",            30,   "MIC MUTE",   0x00, (255, 82, 82)),
        StreamDeckTile(3,  "🔇", "VOL MUTE",     "Master Ton Mute",  "#ff4081", "audio_mute",          29,   "VOL MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(4,  "💬", "DISCORD MUTE", "Ctrl+Shift+M",     "#5865f2", "hotkey_discord_mute", 17,   "DISC MUTE",  0x00, (88, 101, 242)),
        StreamDeckTile(5,  "🎧", "DISC DEAFEN",  "Ctrl+Shift+D",     "#5865f2", "hotkey_discord_deaf", 18,   "DISC DEAF",  0x00, (88, 101, 242)),
        StreamDeckTile(6,  "🎬", "CLIP 30s",     "Alt+F10 Replay",   "#ffab00", "hotkey_clip",         14,   "CLIP 30S",   0x00, (255, 171, 0)),
        StreamDeckTile(7,  "✂", "SCREENSHOT",   "Win+Shift+S Snip", "#00e5ff", "hotkey_screenshot",   26,   "SCREENSHOT", 0x00, (0, 229, 255)),
        StreamDeckTile(8,  "🎯", "STREAM FOKUS", "1-Klick Fokus",    "#a020f0", "focus_stream",        12,   "STRM FOCUS", 0x00, (160, 32, 240)),
        StreamDeckTile(9,  "📋", "CLIPBOARD",    "Win+V Historie",   "#00b8d4", "hotkey_clipboard",    15,   "CLIPBOARD",  0x00, (0, 184, 212)),
        StreamDeckTile(10, "📊", "CPU LOAD",     "1x1 Telemetrie",   "#00e575", "open_taskmgr",        1008, "CPU LOAD",   0x00, (0, 229, 117)),
        StreamDeckTile(11, "🔒", "LOCK PC",      "Win+L Sperren",    "#ff1e32", "lock_pc",             28,   "LOCK PC",    0x00, (255, 30, 50)),
    ],
    "stream_media": [
        StreamDeckTile(0,  "⏯", "PLAY / PAUSE", "Stream / Video",   "#00e575", "media_play_pause",    35,   "PLAY/PAUSE", 0x00, (0, 255, 117)),
        StreamDeckTile(1,  "🎯", "STREAM FOKUS", "Fensterwechsel",   "#00e5ff", "focus_stream",        12,   "STRM FOCUS", 0x00, (0, 229, 255)),
        StreamDeckTile(2,  "⛶", "VOLLBILD (F)", "Stream/YouTube",   "#00b8d4", "browser_fullscreen",  13,   "FULLSCREEN", 0x09, (0, 184, 212)),
        StreamDeckTile(3,  "🔇", "SPEAKER MUTE", "Master Ton",       "#ff4081", "audio_mute",          29,   "VOL MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(4,  "🎙", "MIC MUTE",     "Mikrofon",         "#ff5252", "mic_mute",            30,   "MIC MUTE",   0x00, (255, 82, 82)),
        StreamDeckTile(5,  "🟣", "TWITCH LIVE",  "Stream + RGB",     "#a020f0", "open_twitch",         14,   "TWITCH",     0x00, (160, 32, 240)),
        StreamDeckTile(6,  "🔴", "YOUTUBE",      "Video + RGB",      "#ff1e32", "open_youtube",        15,   "YOUTUBE",    0x00, (255, 30, 50)),
        StreamDeckTile(7,  "🟢", "SPOTIFY",      "Musik Fokus",      "#00ff66", "app_spotify",         16,   "SPOTIFY",    0x00, (0, 255, 102)),
        StreamDeckTile(8,  "💬", "DISCORD MUTE", "Ctrl+Shift+M",     "#5865f2", "hotkey_discord_mute", 17,   "DISC MUTE",  0x00, (88, 101, 242)),
        StreamDeckTile(9,  "🎬", "CLIP 30s",     "Alt+F10 Replay",   "#ffab00", "hotkey_clip",         18,   "CLIP 30S",   0x00, (255, 171, 0)),
        StreamDeckTile(10, "📸", "KB7 SNAPSHOT", "Stream -> LCD",    "#00e5ff", "stream_snapshot",     26,   "SNAPSHOT",   0x00, (0, 229, 255)),
        StreamDeckTile(11, "🔄", "AUTO-STREAM",  "Diashow -> LCD",   "#00e575", "toggle_auto_stream",  19,   "AUTO STRM",  0x00, (0, 229, 117)),
    ],
    "obs_creator": [
        StreamDeckTile(0,  "📡", "LIVE STREAM",  "OBS Start/Stop",   "#ff1e32", "hotkey_obs_stream",   12,   "LIVE STRM",  0x00, (255, 30, 50)),
        StreamDeckTile(1,  "🎥", "RECORDING",    "OBS Rec Toggle",   "#ff5252", "hotkey_obs_rec",      13,   "OBS REC",    0x00, (255, 82, 82)),
        StreamDeckTile(2,  "🎬", "SAVE CLIP",    "Replay Buffer",    "#ffab00", "hotkey_clip",         14,   "SAVE CLIP",  0x00, (255, 171, 0)),
        StreamDeckTile(3,  "🖥", "SZENE 1: MAIN","Ctrl+Alt+F1",      "#00e5ff", "hotkey_scene1",       15,   "SCENE 1",    0x00, (0, 229, 255)),
        StreamDeckTile(4,  "🎮", "SZENE 2: GAME","Ctrl+Alt+F2",      "#00e575", "hotkey_scene2",       16,   "SCENE 2",    0x00, (0, 229, 117)),
        StreamDeckTile(5,  "☕", "SZENE 3: BRB", "Ctrl+Alt+F3",      "#a020f0", "hotkey_scene3",       17,   "BRB SCENE",  0x00, (160, 32, 240)),
        StreamDeckTile(6,  "🎙", "MIC MUTE",     "Hardware 1x1",     "#ff4081", "mic_mute",            30,   "MIC MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(7,  "🔇", "MASTER MUTE",  "Hardware 1x1",     "#ff4081", "audio_mute",          29,   "VOL MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(8,  "💬", "DISC DEAFEN",  "Ctrl+Shift+D",     "#5865f2", "hotkey_discord_deaf", 18,   "DEAFEN",     0x00, (88, 101, 242)),
        StreamDeckTile(9,  "📸", "KB7 SNAPSHOT", "Vorschau -> LCD",  "#00e5ff", "stream_snapshot",     26,   "SNAPSHOT",   0x00, (0, 229, 255)),
        StreamDeckTile(10, "🔥", "CPU LOAD 1x1", "Mini Telemetrie",  "#00e575", "none",                1008, "CPU LOAD",   0x00, (0, 229, 117)),
        StreamDeckTile(11, "⚡", "GPU LOAD 1x1", "Mini Telemetrie",  "#00e575", "none",                1007, "GPU LOAD",   0x00, (0, 229, 117)),
    ],
    "gaming_discord": [
        StreamDeckTile(0,  "🎙", "DISCORD MUTE", "Ctrl+Shift+M",     "#5865f2", "hotkey_discord_mute", 12,   "DISC MUTE",  0x00, (88, 101, 242)),
        StreamDeckTile(1,  "🎧", "DISC DEAFEN",  "Ctrl+Shift+D",     "#5865f2", "hotkey_discord_deaf", 13,   "DISC DEAF",  0x00, (88, 101, 242)),
        StreamDeckTile(2,  "🎬", "INSTANT CLIP", "Alt+F10 Shadow",   "#00ff66", "hotkey_clip",         14,   "CLIP IT",    0x00, (0, 255, 102)),
        StreamDeckTile(3,  "⏺", "GAME REC",     "Win+Alt+R",        "#ff1e32", "hotkey_record",       15,   "GAME REC",   0x00, (255, 30, 50)),
        StreamDeckTile(4,  "⚡", "RAPID TRIG",   "1x1 Switch Mode",  "#00e5ff", "none",                3005, "RAPID TRG",  0x00, (0, 229, 255)),
        StreamDeckTile(5,  "🎯", "SOCD MODE",    "1x1 Snap Tap",     "#00e575", "none",                3008, "SOCD",       0x00, (0, 229, 117)),
        StreamDeckTile(6,  "🔥", "CPU TEMP 1x1", "Mini Sensor",      "#ffab00", "none",                1006, "CPU TEMP",   0x00, (255, 171, 0)),
        StreamDeckTile(7,  "🌡", "GPU TEMP 1x1", "Mini Sensor",      "#ffab00", "none",                1009, "GPU TEMP",   0x00, (255, 171, 0)),
        StreamDeckTile(8,  "📊", "CPU LOAD 1x1", "Mini Sensor",      "#00e575", "none",                1008, "CPU LOAD",   0x00, (0, 229, 117)),
        StreamDeckTile(9,  "🚀", "GPU LOAD 1x1", "Mini Sensor",      "#00e575", "none",                1007, "GPU LOAD",   0x00, (0, 229, 117)),
        StreamDeckTile(10, "🔇", "SPEAKER MUTE", "1x1 Audio",        "#ff4081", "audio_mute",          29,   "VOL MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(11, "🎙", "MIC MUTE",     "1x1 Audio",        "#ff4081", "mic_mute",            30,   "MIC MUTE",   0x00, (255, 64, 129)),
    ],
    "mini_telemetry": [
        StreamDeckTile(0,  "🔥", "CPU TEMP",     "1x1 Mini Kachel",  "#00e575", "none",                1006, "CPU TEMP",   0x00, (0, 229, 117)),
        StreamDeckTile(1,  "📊", "CPU LOAD",     "1x1 Mini Kachel",  "#00e575", "none",                1008, "CPU LOAD",   0x00, (0, 229, 117)),
        StreamDeckTile(2,  "🚀", "GPU LOAD",     "1x1 Mini Kachel",  "#00e5ff", "none",                1007, "GPU LOAD",   0x00, (0, 229, 255)),
        StreamDeckTile(3,  "🌡", "GPU TEMP",     "1x1 Mini Kachel",  "#00e5ff", "none",                1009, "GPU TEMP",   0x00, (0, 229, 255)),
        StreamDeckTile(4,  "🧠", "RAM LOAD",     "1x1 Mini Kachel",  "#a020f0", "none",                1010, "RAM LOAD",   0x00, (160, 32, 240)),
        StreamDeckTile(5,  "⬆", "NET UPLOAD",   "1x1 Mini Kachel",  "#00b8d4", "none",                1011, "NET UP",     0x00, (0, 184, 212)),
        StreamDeckTile(6,  "⬇", "NET DOWN",     "1x1 Mini Kachel",  "#00b8d4", "none",                1012, "NET DOWN",   0x00, (0, 184, 212)),
        StreamDeckTile(7,  "🌐", "NET SPEED",    "1x1 Mini Kachel",  "#00e575", "none",                1013, "NET SPD",    0x00, (0, 229, 117)),
        StreamDeckTile(8,  "⏯", "PLAY / PAUSE", "1x1 Media",        "#00ff66", "media_play_pause",    35,   "PLAY",       0x00, (0, 255, 102)),
        StreamDeckTile(9,  "🔇", "VOL MUTE",     "1x1 Audio",        "#ff4081", "audio_mute",          29,   "VOL MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(10, "🎙", "MIC MUTE",     "1x1 Audio",        "#ff4081", "mic_mute",            30,   "MIC MUTE",   0x00, (255, 64, 129)),
        StreamDeckTile(11, "📈", "TASK MANAGER", "1x1 System",       "#ffab00", "open_taskmgr",        27,   "TASKMGR",    0x00, (255, 171, 0)),
    ],
    "minecraft_hud": [
        StreamDeckTile(0,  "💎", "DIAMONDS: 0",  "Inventar Zähler",   "#00e5ff", "none",                12,   "DIAMONDS",   0x00, (0, 229, 255)),
        StreamDeckTile(1,  "🪙", "ATM / ORES",   "Endgame Metalle",  "#ffb800", "none",                13,   "ALLOY/ATM",  0x00, (255, 184, 0)),
        StreamDeckTile(2,  "❤️", "HP: 20/20",     "100% Leben",       "#00e575", "none",                14,   "HEALTH",     0x00, (0, 229, 117)),
        StreamDeckTile(3,  "🛡️", "ARMOR: 0",     "Schutzwert",       "#00e5ff", "none",                15,   "ARMOR",      0x00, (0, 229, 255)),
        StreamDeckTile(4,  "✨", "XP: LVL 0",    "Fortschritt",      "#00ff66", "none",                16,   "XP LEVEL",   0x00, (0, 255, 102)),
        StreamDeckTile(5,  "🧭", "COORDS: 0, 0", "X, Y, Z Pos",      "#00e575", "hotkey_clipboard",    17,   "COORDS",     0x00, (0, 229, 117)),
        StreamDeckTile(6,  "🌍", "OVERWORLD",    "Dimension",        "#a020f0", "none",                18,   "DIMENSION",  0x00, (160, 32, 240)),
        StreamDeckTile(7,  "⚔️", "TOOL DUR: 100%","Haupthand",        "#ffab00", "none",                19,   "TOOL DUR",   0x00, (255, 171, 0)),
        StreamDeckTile(8,  "🍖", "HUNGER: 20/20","Food & Saturation","#ff9100", "none",                20,   "HUNGER",     0x00, (255, 145, 0)),
        StreamDeckTile(9,  "📸", "SCREENSHOT",   "Win+Shift+S / F2", "#00e5ff", "hotkey_screenshot",   26,   "SCREENSHOT", 0x00, (0, 229, 255)),
        StreamDeckTile(10, "🎙️", "DISC MUTE",    "Ctrl+Shift+M",     "#5865f2", "hotkey_discord_mute", 21,   "DISC MUTE",  0x00, (88, 101, 242)),
        StreamDeckTile(11, "⚡", "RAPID TRG",    "Hall-Effekt Speed","#00e5ff", "none",                3005, "RAPID TRG",  0x00, (0, 229, 255)),
    ],
}


# Win32 Virtual Key Helpers
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12   # Alt
VK_LWIN = 0x5B
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F10 = 0x79
VK_F11 = 0x7A
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002


def _send_vk_combo(*vks: int) -> None:
    """Send a single Virtual Key or hotkey combination via Win32 user32.keybd_event."""
    user32 = ctypes.windll.user32
    for vk in vks:
        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.015)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.015)


def scan_stream_windows() -> List[DetectedStreamWindow]:
    """
    Scan all visible top-level Windows for Twitch, YouTube, OBS Studio, Spotify, or Browser video tabs.
    Returns prioritized `DetectedStreamWindow` objects.
    """
    user32 = ctypes.windll.user32
    results: List[DetectedStreamWindow] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _enum_cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 2:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title or "Turtle Beach KB7" in title or "Program Manager" in title:
            return True

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 200 or h < 150:
            return True

        tl = title.lower()
        platform = None
        badge_col = (0, 229, 255)
        clean = title

        if "twitch" in tl:
            platform = "TWITCH LIVE"
            badge_col = (160, 32, 240)
            clean = title.replace("- Twitch", "").split(" - Google Chrome")[0].split(" - Microsoft")[0].strip()
        elif "youtube" in tl:
            platform = "YOUTUBE STREAM"
            badge_col = (255, 30, 50)
            clean = title.replace("- YouTube", "").split(" - Google Chrome")[0].split(" - Microsoft")[0].strip()
        elif "obs " in tl or tl.startswith("obs") or "streamlabs" in tl:
            platform = "OBS STUDIO"
            badge_col = (0, 229, 117)
        elif "spotify" in tl:
            platform = "SPOTIFY AUDIO"
            badge_col = (0, 255, 102)
        elif any(b in tl for b in ("chrome", "edge", "firefox", "opera", "brave", "vlc", "mpv", "netflix", "disney")):
            platform = "BROWSER STREAM"
            badge_col = (0, 210, 255)
            for suf in (" - Google Chrome", " - Microsoft​ Edge", " - Mozilla Firefox", " - Opera", " - Brave"):
                if suf in clean:
                    clean = clean.split(suf)[0].strip()

        if platform:
            results.append(
                DetectedStreamWindow(
                    hwnd=int(hwnd),
                    title=title,
                    platform=platform,
                    clean_title=clean[:48],
                    badge_color=badge_col,
                    rect=(rect.left, rect.top, rect.right, rect.bottom),
                )
            )
        return True

    try:
        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
    except Exception:
        pass

    # Sort so Twitch, YouTube, OBS come first
    priority = {"TWITCH LIVE": 0, "YOUTUBE STREAM": 1, "OBS STUDIO": 2, "SPOTIFY AUDIO": 3, "BROWSER STREAM": 4}
    results.sort(key=lambda x: priority.get(x.platform, 9))
    return results


def focus_window_by_hwnd(hwnd: int) -> bool:
    """Bring the specified window to the foreground."""
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def capture_screen_snapshot_for_kb7(
    label: str = "LIVE STREAM COMPANION",
    target_window: Optional[DetectedStreamWindow] = None,
) -> Image.Image:
    """
    Capture either the detected Browser/Twitch/YouTube stream window (or primary screen),
    crop/scale to `480x800` for the KB7 framebuffer, and overlay a rich Twitch/Stream Companion HUD.
    """
    bbox = None
    stream_title = "Desktop / Vollbild-Vorschau"
    platform_tag = "LIVE SNAPSHOT"
    badge_rgb = (0, 229, 117)

    if target_window is None:
        detected = scan_stream_windows()
        if detected:
            target_window = detected[0]

    if target_window is not None:
        stream_title = target_window.clean_title or target_window.title[:42]
        platform_tag = target_window.platform
        badge_rgb = target_window.badge_color
        x0, y0, x1, y1 = target_window.rect
        if x1 - x0 > 240 and y1 - y0 > 180 and x0 > -10000:
            bbox = (max(0, x0), max(0, y0), x1, y1)

    try:
        grab = ImageGrab.grab(bbox=bbox) if bbox else ImageGrab.grab()
    except Exception:
        grab = ImageGrab.grab()

    framed = scale_and_center_crop(grab.convert("RGB"), LCD_WIDTH, LCD_HEIGHT)
    rgba = framed.convert("RGBA")

    overlay = Image.new("RGBA", (LCD_WIDTH, LCD_HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Top Stream Companion Header Bar
    odraw.rectangle([(0, 0), (LCD_WIDTH, 46)], fill=(8, 12, 20, 215))
    odraw.line([(0, 46), (LCD_WIDTH, 46)], fill=(*badge_rgb, 240), width=2)

    # Platform Pill Badge
    odraw.rectangle([(12, 9), (148, 36)], fill=(*badge_rgb, 230))
    odraw.text((20, 15), f"● {platform_tag[:14]}", fill=(0, 0, 0, 255))

    # Stream Title & Timestamp
    ts = time.strftime("%H:%M:%S")
    odraw.text((158, 10), stream_title[:36], fill=(240, 246, 252, 255))
    odraw.text((158, 25), f"KB7 Stream Companion  •  {ts}", fill=(140, 160, 185, 255))

    return Image.alpha_composite(rgba, overlay).convert("RGB")


class SmartStreamDeckManager:
    """
    Manages the 12-tile Smart Stream Deck state, profile persistence,
    hardware synchronization (Page 3 on KB7), and host action execution.
    """

    def __init__(self) -> None:
        self.active_profile: str = "common_deck"
        self.ui_tile_size: str = "small"      # "small" (Kompakt), "medium", "large"
        self.hw_small_tiles: bool = True      # True = 1x1 small tiles (all 12 visible), False = 2x1 large tiles
        self.target_hw_page: int = 3          # Target Hardware Page (1, 2, or 3) on KB7 display
        self.auto_stream_enabled: bool = False
        self.auto_stream_mode: str = "mini"   # "mini" (142x148 Slot 0x40 fast) or "full" (480x800 Slot 0x00)
        self.auto_stream_interval: int = 10   # Seconds between snapshots in full mode
        self.tiles: List[StreamDeckTile] = [
            StreamDeckTile(**asdict(t)) for t in STREAMDECK_PROFILES["common_deck"]
        ]
        self.load_config()

    def load_profile(self, profile_name: str) -> List[StreamDeckTile]:
        if profile_name in STREAMDECK_PROFILES:
            self.active_profile = profile_name
            if profile_name == "minecraft_hud":
                if not self.refresh_from_minecraft():
                    self.tiles = [StreamDeckTile(**asdict(t)) for t in STREAMDECK_PROFILES[profile_name]]
            else:
                self.tiles = [StreamDeckTile(**asdict(t)) for t in STREAMDECK_PROFILES[profile_name]]
            self.save_config()
        return self.tiles

    def save_config(self) -> None:
        try:
            data = {
                "active_profile": self.active_profile,
                "ui_tile_size": self.ui_tile_size,
                "hw_small_tiles": self.hw_small_tiles,
                "target_hw_page": self.target_hw_page,
                "auto_stream_mode": self.auto_stream_mode,
                "auto_stream_interval": self.auto_stream_interval,
                "tiles": [asdict(t) for t in self.tiles],
            }
            STREAMDECK_CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_config(self) -> None:
        if not STREAMDECK_CONFIG_PATH.exists():
            return
        try:
            data = json.loads(STREAMDECK_CONFIG_PATH.read_text(encoding="utf-8"))
            self.active_profile = data.get("active_profile", "stream_media")
            self.ui_tile_size = data.get("ui_tile_size", "small")
            self.hw_small_tiles = bool(data.get("hw_small_tiles", True))
            self.target_hw_page = int(data.get("target_hw_page", 3))
            self.auto_stream_mode = data.get("auto_stream_mode", "mini")
            self.auto_stream_interval = int(data.get("auto_stream_interval", 10))
            raw_tiles = data.get("tiles", [])
            if len(raw_tiles) == 12:
                loaded = []
                for idx, rt in enumerate(raw_tiles):
                    rt["rgb_sync"] = tuple(rt.get("rgb_sync", (0, 229, 255)))
                    loaded.append(StreamDeckTile(**rt))
                self.tiles = loaded
        except Exception:
            pass

    def to_hw_slots_config(self) -> List[dict]:
        """Convert the 12 StreamDeckTile objects into hardware slot dicts for `apply_streamdeck_page`."""
        return [
            {
                "slot": t.slot,
                "hw_app_id": t.hw_app_id,
                "hw_label": t.hw_label,
                "hid_code": t.hid_code,
            }
            for t in self.tiles
        ]

    def refresh_from_minecraft(self) -> bool:
        """
        If the active profile is 'minecraft_hud', refreshes the 12 tiles dynamically
        from live Minecraft telemetry (~/.kb7_minecraft_stats.json).
        """
        if self.active_profile != "minecraft_hud":
            return False
        try:
            from .minecraft import load_minecraft_stats, generate_minecraft_tiles
            stats = load_minecraft_stats()
            self.tiles = generate_minecraft_tiles(stats)
            return True
        except Exception:
            return False

    def execute_tile_action(
        self,
        slot_index: int,
        mixer=None,
        steelseries=None,
        snapshot_callback: Optional[Callable[[], None]] = None,
        toggle_auto_stream_callback: Optional[Callable[[], None]] = None,
        device=None,
    ) -> str:
        """
        Execute the Smart Action assigned to `slot_index` (`0..11`) and return a status message.
        """
        if not (0 <= slot_index < len(self.tiles)):
            return "Invalid slot"

        tile = self.tiles[slot_index]
        act = tile.action_id

        # Optional RGB sync on mouse when triggering a Stream Deck tile
        if steelseries and getattr(steelseries, "connected", False) and tile.rgb_sync:
            try:
                r, g, b = tile.rgb_sync
                steelseries.set_color(r, g, b)
            except Exception:
                pass

        if act == "media_play_pause":
            _send_vk_combo(VK_MEDIA_PLAY_PAUSE)
            return "⏯ Media/Stream Play/Pause ausgelöst"
        elif act == "media_prev":
            _send_vk_combo(VK_MEDIA_PREV_TRACK)
            return "⏮ Vorheriger Track ausgelöst"
        elif act == "media_next":
            _send_vk_combo(VK_MEDIA_NEXT_TRACK)
            return "⏭ Nächster Track ausgelöst"
        elif act == "media_stop":
            _send_vk_combo(VK_MEDIA_STOP)
            return "⏹ Media Stop ausgelöst"
        elif act == "focus_stream":
            wins = scan_stream_windows()
            if wins:
                focus_window_by_hwnd(wins[0].hwnd)
                return f"🎯 Fokus auf [{wins[0].platform}] {wins[0].clean_title}"
            return "🎯 Kein aktives Stream-/Browser-Fenster gefunden"
        elif act == "browser_fullscreen":
            wins = scan_stream_windows()
            if wins:
                focus_window_by_hwnd(wins[0].hwnd)
                time.sleep(0.08)
            _send_vk_combo(ord("F"))
            return "⛶ Stream-Vollbild (Taste F) umgeschaltet"
        elif act == "twitch_theater":
            wins = scan_stream_windows()
            if wins:
                focus_window_by_hwnd(wins[0].hwnd)
                time.sleep(0.08)
            _send_vk_combo(VK_MENU, ord("T"))
            return "🎭 Twitch Theater-Modus (Alt+T) umgeschaltet"
        elif act == "vol_up":
            _send_vk_combo(VK_VOLUME_UP)
            _send_vk_combo(VK_VOLUME_UP)
            return "🔊 Lautstärke +5%"
        elif act == "vol_down":
            _send_vk_combo(VK_VOLUME_DOWN)
            _send_vk_combo(VK_VOLUME_DOWN)
            return "🔉 Lautstärke -5%"
        elif act == "audio_mute":
            if mixer:
                try:
                    cur = mixer.get_master_mute()
                    mixer.set_master_mute(not cur)
                    return f"🔇 Master Audio {'Stummgeschaltet' if not cur else 'Aktiv'}"
                except Exception:
                    pass
            _send_vk_combo(VK_VOLUME_MUTE)
            return "🔇 Master Mute umgeschaltet"
        elif act == "mic_mute":
            if mixer:
                try:
                    cur = mixer.get_mic_mute()
                    mixer.set_mic_mute(not cur)
                    return f"🎙 Mikrofon {'Stummgeschaltet' if not cur else 'Aktiv'}"
                except Exception:
                    pass
            _send_vk_combo(VK_CONTROL, VK_SHIFT, ord("M"))
            return "🎙 Mikrofon Mute umgeschaltet"
        elif act == "open_twitch":
            webbrowser.open("https://www.twitch.tv")
            return "🟣 Twitch im Browser geöffnet (+ Neon Purple RGB)"
        elif act == "open_youtube":
            webbrowser.open("https://www.youtube.com")
            return "🔴 YouTube im Browser geöffnet (+ Crimson Red RGB)"
        elif act == "app_spotify":
            try:
                subprocess.Popen(["cmd", "/c", "start", "spotify:"], shell=False)
            except Exception:
                webbrowser.open("https://open.spotify.com")
            return "🟢 Spotify geöffnet / fokussiert"
        elif act == "app_discord":
            try:
                subprocess.Popen(["cmd", "/c", "start", "discord:"], shell=False)
            except Exception:
                webbrowser.open("https://discord.com/app")
            return "💬 Discord geöffnet / fokussiert"
        elif act == "hotkey_discord_mute":
            _send_vk_combo(VK_CONTROL, VK_SHIFT, ord("M"))
            return "🎙 Discord Mic Mute (Ctrl+Shift+M) gesendet"
        elif act == "hotkey_discord_deaf":
            _send_vk_combo(VK_CONTROL, VK_SHIFT, ord("D"))
            return "🎧 Discord Deafen (Ctrl+Shift+D) gesendet"
        elif act == "hotkey_clip":
            _send_vk_combo(VK_MENU, VK_F10)
            return "🎬 Instant Replay Clip (Alt+F10) gespeichert"
        elif act == "hotkey_record":
            _send_vk_combo(VK_LWIN, VK_MENU, ord("R"))
            return "⏺ Game Bar Aufnahme (Win+Alt+R) umgeschaltet"
        elif act == "hotkey_obs_stream":
            _send_vk_combo(VK_CONTROL, VK_SHIFT, VK_F10)
            return "📡 OBS Stream Start/Stop (Ctrl+Shift+F10) gesendet"
        elif act == "hotkey_obs_rec":
            _send_vk_combo(VK_CONTROL, VK_SHIFT, VK_F11)
            return "🎥 OBS Aufnahme Start/Stop (Ctrl+Shift+F11) gesendet"
        elif act == "hotkey_scene1":
            _send_vk_combo(VK_CONTROL, VK_MENU, VK_F1)
            return "🖥 OBS Szene 1 (Ctrl+Alt+F1) aktiviert"
        elif act == "hotkey_scene2":
            _send_vk_combo(VK_CONTROL, VK_MENU, VK_F2)
            return "🎮 OBS Szene 2 (Ctrl+Alt+F2) aktiviert"
        elif act == "hotkey_scene3":
            _send_vk_combo(VK_CONTROL, VK_MENU, VK_F3)
            return "☕ OBS Szene 3 (Ctrl+Alt+F3) aktiviert"
        elif act == "hotkey_screenshot":
            _send_vk_combo(VK_LWIN, VK_SHIFT, ord("S"))
            return "✂ Screenshot Snipping Tool (Win+Shift+S) geöffnet"
        elif act == "hotkey_clipboard":
            _send_vk_combo(VK_LWIN, ord("V"))
            return "📋 Zwischenablageverlauf (Win+V) geöffnet"
        elif act == "show_desktop":
            _send_vk_combo(VK_LWIN, ord("D"))
            return "🖥 Desktop anzeigen (Win+D) umgeschaltet"
        elif act == "open_terminal":
            try:
                subprocess.Popen(["wt.exe"], shell=False)
            except Exception:
                subprocess.Popen(["powershell.exe"], shell=False)
            return "💻 Windows Terminal / PowerShell geöffnet"
        elif act == "switch_hw_page":
            if device:
                try:
                    cur_p = getattr(device, "_active_page", 1)
                    next_p = 1 if cur_p >= 3 else cur_p + 1
                    device.set_active_page(next_p)
                    return f"📄 KB7 LCD auf Seite {next_p} umgeschaltet"
                except Exception as e:
                    return f"📄 Seitenwechsel Fehler: {e}"
            return "📄 Display-Seite weitergeschaltet"
        elif act == "stream_snapshot":
            if snapshot_callback:
                snapshot_callback()
            return "📸 Übertrage Live-Stream-Snapshot auf das KB7 Display..."
        elif act == "toggle_auto_stream":
            if toggle_auto_stream_callback:
                toggle_auto_stream_callback()
            return "🔄 Auto-Stream / Diashow aufs KB7 Display umgeschaltet"
        elif act == "open_taskmgr":
            subprocess.Popen(["taskmgr.exe"], shell=False)
            return "📊 Task-Manager geöffnet"
        elif act == "open_calc":
            subprocess.Popen(["calc.exe"], shell=False)
            return "🧮 Taschenrechner geöffnet"
        elif act == "open_explorer":
            subprocess.Popen(["explorer.exe"], shell=False)
            return "📁 Datei-Explorer geöffnet"
        elif act == "lock_pc":
            ctypes.windll.user32.LockWorkStation()
            return "🔒 PC gesperrt"
        else:
            return f"ℹ Kachel '{tile.title}' (Slot {slot_index}) aktiv"
