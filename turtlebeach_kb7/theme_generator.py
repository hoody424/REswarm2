"""
Turtle Beach KB7 - Display Theme & Wallpaper Designer.

Procedurally generates high-resolution, pixel-perfect 800x480 custom UI designs
and HUD wallpapers tailored specifically for the KB7's 4.3" touch display.
Includes presets:
  1. 'tactical_hud'   - Cyberpunk / Sci-Fi Tactical Cockpit (Cyan & Amber)
  2. 'audiophile_dark' - High-End Studio Mixer & VU Meter Deck (Brushed Charcoal & Gold)
  3. 'neon_cyberpunk'  - Synthwave / Cyberdeck (Neon Magenta & Cyan with Grid Matrix)
"""

import os
import math
from typing import Tuple, Optional
from PIL import Image, ImageDraw, ImageFont

from .image import convert_to_rgb565

WIDTH = 800
HEIGHT = 480


def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Attempts to load a clean Windows system font, falling back to default."""
    paths = [
        os.path.join(r"C:\Windows\Fonts", name),
        os.path.join(r"C:\Windows\Fonts", "bahnschrift.ttf"),
        os.path.join(r"C:\Windows\Fonts", "segoeuib.ttf"),
        os.path.join(r"C:\Windows\Fonts", "arialbd.ttf"),
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def generate_tactical_hud() -> Image.Image:
    """
    Preset 1: Tactical HUD Cockpit.
    Features: Sci-Fi angled telemetry header, 6 illuminated widget docking brackets,
    circuit grid lines, audio spectrum waveform, and system status badges.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), "#080c14")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 20)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 10)

    # 1. Background Gradient (Dark Navy/Obsidian)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(8 + 8 * math.sin(ratio * math.pi))
        g = int(12 + 10 * ratio)
        b = int(20 + 25 * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # 2. Tech Grid Lines (Subtle Cyan Matrix)
    grid_color = (0, 70, 95)
    for x in range(0, WIDTH, 40):
        draw.line([(x, 40), (x, HEIGHT - 25)], fill=(0, 25, 38))
    for y in range(40, HEIGHT - 25, 40):
        draw.line([(0, y), (WIDTH, y)], fill=(0, 25, 38))

    # 3. Top Header Telemetry Bar
    draw.polygon([(0, 0), (WIDTH, 0), (WIDTH, 36), (WIDTH - 40, 36), (WIDTH - 60, 42), (60, 42), (40, 36), (0, 36)], fill=(12, 22, 36))
    draw.line([(0, 36), (40, 36), (60, 42), (WIDTH - 60, 42), (WIDTH - 40, 36), (WIDTH, 36)], fill=(0, 229, 255), width=2)

    # Header Title & Accents
    draw.text((30, 10), "TURTLE BEACH", font=font_bold, fill=(255, 179, 0))
    draw.text((140, 8), "// COMMAND KB7 TACTICAL HUD", font=font_title, fill=(0, 229, 255))

    # Status Badges
    draw.ellipse([(620, 15), (628, 23)], fill=(0, 230, 118)) # Green dot
    draw.text((634, 13), "ONLINE", font=font_small, fill=(0, 230, 118))
    draw.text((700, 13), "8000Hz SCAN", font=font_small, fill=(255, 179, 0))

    # 4. Widget Docking Brackets (6 Slots: 3 Top, 3 Bottom)
    # Dimensions: 220 wide x 165 high
    slots = [
        (40, 60, "SLOT 01 // AUDIO CORE", "PRIMARY VOLUME & MUTE"),
        (290, 60, "SLOT 02 // MEDIA HUD", "PLAYBACK & PLAYLIST"),
        (540, 60, "SLOT 03 // TELEMETRY", "CPU / GPU / VRAM LOAD"),
        (40, 250, "SLOT 04 // COMMS HUB", "DISCORD & VOICE CHAT"),
        (290, 250, "SLOT 05 // SYSTEM STATS", "RAM USAGE & THERMALS"),
        (540, 250, "SLOT 06 // QUICK ACCESS", "MACRO & SCREEN CONTROLS"),
    ]

    for sx, sy, label, sub in slots:
        sw, sh = 220, 165

        # Inner dark card fill
        draw.rectangle([(sx, sy), (sx + sw, sy + sh)], fill=(14, 24, 38))

        # Glowing corner brackets (Chamfered look)
        c_len = 16
        # Top-Left
        draw.line([(sx, sy + c_len), (sx, sy), (sx + c_len, sy)], fill=(0, 229, 255), width=2)
        # Top-Right
        draw.line([(sx + sw - c_len, sy), (sx + sw, sy), (sx + sw, sy + c_len)], fill=(0, 229, 255), width=2)
        # Bottom-Left
        draw.line([(sx, sy + sh - c_len), (sx, sy + sh), (sx + c_len, sy + sh)], fill=(0, 229, 255), width=2)
        # Bottom-Right
        draw.line([(sx + sw - c_len, sy + sh), (sx + sw, sy + sh), (sx + sw, sy + sh - c_len)], fill=(0, 229, 255), width=2)

        # Subtle border line
        draw.rectangle([(sx, sy), (sx + sw, sy + sh)], outline=(20, 50, 75), width=1)

        # Slot Label Header Tab
        draw.polygon([(sx, sy), (sx + 150, sy), (sx + 160, sy + 18), (sx, sy + 18)], fill=(20, 42, 64))
        draw.text((sx + 8, sy + 3), label, font=font_small, fill=(0, 229, 255))

        # Crosshairs in center
        cx, cy = sx + sw // 2, sy + sh // 2
        draw.line([(cx - 8, cy), (cx + 8, cy)], fill=(0, 100, 130), width=1)
        draw.line([(cx, cy - 8), (cx, cy + 8)], fill=(0, 100, 130), width=1)
        draw.ellipse([(cx - 15, cy - 15), (cx + 15, cy + 15)], outline=(0, 80, 110), width=1)

        # Subtitle at bottom
        draw.text((sx + 10, sy + sh - 16), sub, font=font_small, fill=(120, 150, 180))

    # 5. Audio Spectrum Equalizer Wave Graphic (Center Divider)
    bars = 32
    bar_w = 4
    start_x = 330
    for i in range(bars):
        h = int(12 + 10 * math.sin(i * 0.4) * math.cos(i * 0.2))
        bx = start_x + i * 5
        by = 232 - h // 2
        color = (0, 229, 255) if i < 22 else (255, 179, 0)
        draw.line([(bx, by), (bx, by + h)], fill=color, width=2)

    # 6. Bottom Status Bar
    draw.rectangle([(0, HEIGHT - 22), (WIDTH, HEIGHT)], fill=(10, 16, 26))
    draw.line([(0, HEIGHT - 22), (WIDTH, HEIGHT - 22)], fill=(0, 150, 180), width=1)
    draw.text((25, HEIGHT - 18), "DUAL-MCU ARCHITECTURE [SONIX SNC73xx + ARTERY AT423] // HALL-EFFECT RAPID TRIGGER READY", font=font_small, fill=(100, 140, 180))
    draw.text((710, HEIGHT - 18), "800x480 WVGA", font=font_small, fill=(255, 179, 0))

    return img


def generate_audiophile_dark() -> Image.Image:
    """
    Preset 2: Audiophile Dark / Studio Mixing Console.
    Features: Elegant brushed carbon, gold VU meter scales, dual analog-style needle dials,
    and warm studio accents.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), "#0f1115")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 18)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 10)

    # 1. Brushed Dark Chassis Texture
    for y in range(HEIGHT):
        shade = int(14 + 6 * math.sin(y * 0.1) + 4 * (y / HEIGHT))
        draw.line([(0, y), (WIDTH, y)], fill=(shade, shade + 2, shade + 4))

    # 2. Golden Framing Header
    draw.rectangle([(0, 0), (WIDTH, 36)], fill=(22, 25, 32))
    draw.line([(0, 36), (WIDTH, 36)], fill=(230, 165, 30), width=2)

    draw.text((25, 8), "TURTLE BEACH", font=font_bold, fill=(230, 165, 30))
    draw.text((150, 8), "COMMAND SERIES // MASTER AUDIO CONSOLE", font=font_title, fill="#ffffff")
    draw.text((670, 11), "WASAPI DIRECT", font=font_small, fill=(230, 165, 30))

    # 3. Dual Analog VU Meters in Center
    vu_boxes = [(100, 55, 270, 140, "CHANNEL A // MASTER L"), (430, 55, 270, 140, "CHANNEL B // MASTER R")]
    for vx, vy, vw, vh, title in vu_boxes:
        draw.rectangle([(vx, vy), (vx + vw, vy + vh)], fill=(24, 28, 36), outline=(60, 68, 85), width=2)
        # Inner dial face
        draw.rectangle([(vx + 10, vy + 10), (vx + vw - 10, vy + vh - 25)], fill=(32, 38, 48))
        draw.text((vx + 16, vy + vh - 20), title, font=font_small, fill=(200, 160, 60))

        # Arc for VU meter scale
        arc_box = [vx + 30, vy + 15, vx + vw - 30, vy + vh + 10]
        draw.arc(arc_box, start=200, end=340, fill=(120, 130, 150), width=2)

        # Scale tick marks
        for deg in range(210, 335, 15):
            rad = math.radians(deg)
            cx, cy = vx + vw // 2, vy + vh - 10
            r1 = 70
            r2 = 82
            x1 = cx + r1 * math.cos(rad)
            y1 = cy + r1 * math.sin(rad)
            x2 = cx + r2 * math.cos(rad)
            y2 = cy + r2 * math.sin(rad)
            color = (255, 80, 80) if deg > 300 else (230, 165, 30)
            draw.line([(x1, y1), (x2, y2)], fill=color, width=2)

        # Golden Needle
        needle_deg = 275
        n_rad = math.radians(needle_deg)
        cx, cy = vx + vw // 2, vy + vh - 10
        nx = cx + 80 * math.cos(n_rad)
        ny = cy + 80 * math.sin(n_rad)
        draw.line([(cx, cy), (nx, ny)], fill=(255, 190, 40), width=3)
        draw.ellipse([(cx - 6, cy - 6), (cx + 6, cy + 6)], fill=(255, 190, 40))

    # 4. Lower Channel Fader Slots (4 Cards)
    faders = [
        (40, 220, "FADER 1", "DISCORD"),
        (225, 220, "FADER 2", "BROWSER / TWITCH"),
        (410, 220, "FADER 3", "GAME AUDIO"),
        (595, 220, "FADER 4", "SYSTEM / SPOTIFY"),
    ]

    for fx, fy, title, sub in faders:
        fw, fh = 165, 225
        draw.rectangle([(fx, fy), (fx + fw, fy + fh)], fill=(20, 24, 32), outline=(45, 52, 65), width=2)
        # Gold header tab
        draw.rectangle([(fx, fy), (fx + fw, fy + 26)], fill=(30, 36, 48))
        draw.text((fx + 12, fy + 6), title, font=font_small, fill=(230, 165, 30))
        draw.text((fx + 12, fy + fh - 24), sub, font=font_small, fill=(240, 240, 240))

        # Vertical Fader track slot
        slot_x = fx + fw // 2
        draw.line([(slot_x, fy + 40), (slot_x, fy + fh - 40)], fill=(10, 12, 16), width=8)
        draw.line([(slot_x, fy + 40), (slot_x, fy + fh - 40)], fill=(60, 70, 85), width=2)

        # Fader knob (Golden cap)
        knob_y = fy + 80
        draw.rectangle([(slot_x - 18, knob_y - 12), (slot_x + 18, knob_y + 12)], fill=(230, 165, 30), outline=(255, 220, 100), width=1)
        draw.line([(slot_x - 14, knob_y), (slot_x + 14, knob_y)], fill=(50, 40, 10), width=2)

    # Bottom status bar
    draw.rectangle([(0, HEIGHT - 20), (WIDTH, HEIGHT)], fill=(16, 18, 24))
    draw.line([(0, HEIGHT - 20), (WIDTH, HEIGHT - 20)], fill=(230, 165, 30), width=1)
    draw.text((25, HEIGHT - 16), "STUDIO HIGH-DEFINITION SOUND INTERFACE // HARDWARE ROTARY DIAL SYNC", font=font_small, fill=(180, 180, 180))

    return img


def generate_neon_cyberpunk() -> Image.Image:
    """
    Preset 3: Neon Cyberpunk / Synthwave.
    Features: Electric Magenta & Cyber Cyan accents, 3D perspective floor grid,
    Japanese katakana logo, and glowing HUD brackets.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), "#0a0614")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 22)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 10)

    # 1. Neon Sunset Gradient
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(15 + 40 * ratio)
        g = int(8 + 10 * ratio)
        b = int(35 + 45 * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # 2. Perspective Synthwave Grid at Bottom
    horizon = 260
    vanishing_x = WIDTH // 2
    # Perspective rays
    for x in range(-200, WIDTH + 300, 60):
        draw.line([(vanishing_x, horizon), (x, HEIGHT)], fill=(255, 0, 128), width=1)
    # Horizontal grid lines with increasing spacing
    y_step = horizon
    spacing = 6
    while y_step < HEIGHT:
        draw.line([(0, int(y_step)), (WIDTH, int(y_step))], fill=(0, 240, 255), width=1)
        spacing *= 1.35
        y_step += spacing

    # 3. Top Glowing Banner
    draw.rectangle([(0, 0), (WIDTH, 42)], fill=(18, 12, 32))
    draw.line([(0, 42), (WIDTH, 42)], fill=(255, 0, 128), width=2)
    draw.line([(0, 44), (WIDTH, 44)], fill=(0, 240, 255), width=1)

    draw.text((30, 10), "TURTLE BEACH // コマンド KB7", font=font_bold, fill=(255, 0, 128))
    draw.text((300, 8), "CYBERDECK HUD v2.5", font=font_title, fill=(0, 240, 255))
    draw.text((680, 13), "[SYS: ACTIVE]", font=font_small, fill=(0, 255, 170))

    # 4. Cyber Slots (6 Floating Hologram Cards)
    slots = [
        (40, 65, "CH_01 // AUDIO MUTE"),
        (290, 65, "CH_02 // MEDIA STREAM"),
        (540, 65, "CH_03 // CORE TELEMETRY"),
        (40, 250, "CH_04 // DISCORD VOICE"),
        (290, 250, "CH_05 // SYSTEM THERMALS"),
        (540, 250, "CH_06 // MACRO OVERDRIVE"),
    ]

    for sx, sy, title in slots:
        sw, sh = 220, 165
        # Hologram Fill
        draw.rectangle([(sx, sy), (sx + sw, sy + sh)], fill=(24, 16, 44))

        # Double Neon Borders (Magenta outer, Cyan inner)
        draw.rectangle([(sx, sy), (sx + sw, sy + sh)], outline=(255, 0, 128), width=2)
        draw.rectangle([(sx + 3, sy + 3), (sx + sw - 3, sy + sh - 3)], outline=(0, 240, 255), width=1)

        # Angled corner accents
        c = 14
        draw.polygon([(sx, sy), (sx + c, sy), (sx, sy + c)], fill=(0, 240, 255))
        draw.polygon([(sx + sw, sy), (sx + sw - c, sy), (sx + sw, sy + c)], fill=(255, 0, 128))
        draw.polygon([(sx, sy + sh), (sx + c, sy + sh), (sx, sy + sh - c)], fill=(255, 0, 128))
        draw.polygon([(sx + sw, sy + sh), (sx + sw - c, sy + sh), (sx + sw, sy + sh - c)], fill=(0, 240, 255))

        # Title Tab
        draw.rectangle([(sx + 10, sy + 8), (sx + sw - 10, sy + 28)], fill=(38, 24, 68))
        draw.text((sx + 16, sy + 12), title, font=font_small, fill=(0, 240, 255))

    return img


THEME_PRESETS = {
    "tactical_hud": generate_tactical_hud,
    "audiophile_dark": generate_audiophile_dark,
    "neon_cyberpunk": generate_neon_cyberpunk,
}


def build_and_save_themes(output_dir: str) -> dict:
    """Builds all 3 themes and saves them as PNG images in output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    for name, gen_fn in THEME_PRESETS.items():
        img = gen_fn()
        path = os.path.join(output_dir, f"{name}.png")
        img.save(path)
        paths[name] = path
    return paths
