"""
Turtle Beach KB7 - Display Theme & Wallpaper Designer.

Procedurally generates anti-aliased, high-resolution, pixel-perfect 800x480 custom UI designs
and HUD wallpapers tailored specifically for the KB7's 4.3" touch display.

Uses 2x Super-Sampling Anti-Aliasing (SSAA 1600x960 -> 800x480 via Lanczos) and
Bayer-dithered RGB565 encoding to eliminate jagged edges and color banding.

Themes:
  Green Themes:
    1. 'matrix_cyberdeck'  - Phosphorescent Green Digital Code Rain & Mainframe HUD
    2. 'toxic_radar'       - Apex / Mech Tactical HUD with 360° Sonar & Honeycomb Carbon
    3. 'biohazard_reactor' - Quantum Fusion / Plasma Biohazard Core & Circuit Conduits
    4. 'emerald_synthwave' - Retro-Futuristic Emerald Wireframe Grid & Rising Neon Sun
  Classic Themes:
    5. 'tactical_hud'      - Sci-Fi Cockpit Telemetry (Cyan & Amber)
    6. 'audiophile_dark'   - Studio Mixer Console & Golden VU Meters
    7. 'neon_cyberpunk'    - Synthwave Electric Magenta & Cyan Horizon
"""

import os
import math
import random
from typing import Tuple, Optional, Dict, Callable
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .image import convert_to_rgb565

WIDTH = 800
HEIGHT = 480
SSAA_W = 1600
SSAA_H = 960


def _get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """Attempts to load a clean Windows system font at 2x SSAA scale, falling back gracefully."""
    paths = [
        os.path.join(r"C:\Windows\Fonts", name),
        os.path.join(r"C:\Windows\Fonts", "bahnschrift.ttf"),
        os.path.join(r"C:\Windows\Fonts", "segoeuib.ttf"),
        os.path.join(r"C:\Windows\Fonts", "consolab.ttf"),
        os.path.join(r"C:\Windows\Fonts", "arialbd.ttf"),
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size * 2)
            except Exception:
                pass
    return ImageFont.load_default()


# =============================================================================
# THEME 1: MATRIX CYBERDECK (Phosphorescent Green Code Rain & Terminal HUD)
# =============================================================================

def generate_matrix_cyberdeck() -> Image.Image:
    """
    Preset: Matrix Cyberdeck.
    Features: Cascading streams of digital matrix code rain in phosphorescent emerald green,
    depth-layered glyphs with brilliant white-green leading heads, phosphor CRT glow,
    cyberdeck terminal framing, and subtle scanline texture.
    """
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#020703")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 20)
    font_bold = _get_font("bahnschrift.ttf", 12)
    font_code = _get_font("consolab.ttf", 11)
    font_small = _get_font("consolab.ttf", 9)

    # 1. Subtle Radial Phosphor Glow in Center
    glow = Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    cx, cy = SSAA_W // 2, SSAA_H // 2
    for r in range(400, 0, -40):
        alpha = int(14 * (1.0 - r / 400.0))
        g_draw.ellipse([(cx - r * 2, cy - r), (cx + r * 2, cy + r)], fill=(0, 255, 102, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(Image.composite(glow, Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0)), glow), (0, 0), glow)

    # 2. Digital Matrix Code Rain Streams
    # Deterministic seed so theme renders consistently
    rng = random.Random(7355608)
    chars = "0123456789ABCDEFЖΨΩλπ∑µ<>[]{}:;*+-_/#@%&$=~"
    cols = 48
    col_w = SSAA_W // cols

    for c in range(cols):
        x = c * col_w + 6
        # Background faint stream
        if rng.random() > 0.35:
            start_y = rng.randint(80, 500)
            length = rng.randint(8, 20)
            for i in range(length):
                y = start_y + i * 24
                if y > SSAA_H - 60:
                    break
                ch = rng.choice(chars)
                draw.text((x, y), ch, font=font_code, fill=(0, 55, 22))

        # Midground & Foreground primary stream
        start_y = rng.randint(90, 420)
        length = rng.randint(12, 28)
        for i in range(length):
            y = start_y + i * 24
            if y > SSAA_H - 50:
                break
            ch = rng.choice(chars)
            # Leading head char is brilliant white-green
            if i == length - 1:
                color = (235, 255, 240)
            elif i >= length - 3:
                color = (0, 255, 102)
            elif i >= length - 8:
                color = (0, 200, 75)
            elif i >= length - 16:
                color = (0, 140, 50)
            else:
                color = (0, 80, 30)
            draw.text((x, y), ch, font=font_code, fill=color)

    # 3. Top Cyberdeck Header Bar
    draw.polygon([
        (0, 0), (SSAA_W, 0), (SSAA_W, 76),
        (SSAA_W - 80, 76), (SSAA_W - 120, 88),
        (120, 88), (80, 76), (0, 76)
    ], fill=(8, 22, 12))
    draw.line([(0, 76), (80, 76), (120, 88), (SSAA_W - 120, 88), (SSAA_W - 80, 76), (SSAA_W, 76)], fill=(0, 255, 102), width=4)

    # Top Header Text
    draw.text((50, 22), "TURTLE BEACH", font=font_bold, fill=(0, 230, 90))
    draw.text((250, 18), "// ROOT TERMINAL // MATRIX CYBERDECK 8000Hz", font=font_title, fill="#ffffff")

    # Status Badges
    draw.ellipse([(SSAA_W - 320, 30), (SSAA_W - 304, 46)], fill=(0, 255, 102))
    draw.text((SSAA_W - 290, 26), "CIPHER: ONLINE", font=font_small, fill=(0, 255, 102))
    draw.text((SSAA_W - 140, 26), "SYS: ROOT", font=font_small, fill=(200, 255, 210))

    # 4. Docking Brackets with Chamfered Corners (Framing the 7 Display Slots)
    # 7 slot brackets scaled to 2x: Slots 0..3 top row, 4..6 bottom row
    slot_boxes = [
        (60, 130, 330, 360, "SLOT 01 // CORE A"),
        (430, 130, 330, 360, "SLOT 02 // CORE B"),
        (800, 130, 330, 360, "SLOT 03 // CORE C"),
        (1170, 130, 370, 360, "SLOT 04 // CORE D"),
        (60, 530, 460, 360, "SLOT 05 // BUS 01"),
        (560, 530, 480, 360, "SLOT 06 // BUS 02"),
        (1080, 530, 460, 360, "SLOT 07 // BUS 03"),
    ]

    for sx, sy, sw, sh, label in slot_boxes:
        # Dark inner plate
        draw.rectangle([(sx, sy), (sx + sw, sy + sh)], fill=(4, 15, 7))
        draw.rectangle([(sx, sy), (sx + sw, sy + sh)], outline=(12, 45, 22), width=2)

        # Luminous corner notches
        c = 28
        # Top-Left
        draw.line([(sx, sy + c), (sx, sy), (sx + c, sy)], fill=(0, 255, 102), width=4)
        # Top-Right
        draw.line([(sx + sw - c, sy), (sx + sw, sy), (sx + sw, sy + c)], fill=(0, 255, 102), width=4)
        # Bottom-Left
        draw.line([(sx, sy + sh - c), (sx, sy + sh), (sx + c, sy + sh)], fill=(0, 255, 102), width=4)
        # Bottom-Right
        draw.line([(sx + sw - c, sy + sh), (sx + sw, sy + sh), (sx + sw, sy + sh - c)], fill=(0, 255, 102), width=4)

        # Small header badge
        draw.polygon([(sx, sy), (sx + 200, sy), (sx + 220, sy + 32), (sx, sy + 32)], fill=(10, 35, 18))
        draw.text((sx + 14, sy + 6), label, font=font_small, fill=(0, 255, 102))

    # 5. Bottom Status Footer
    draw.rectangle([(0, SSAA_H - 44), (SSAA_W, SSAA_H)], fill=(6, 16, 9))
    draw.line([(0, SSAA_H - 44), (SSAA_W, SSAA_H - 44)], fill=(0, 200, 80), width=2)
    draw.text((40, SSAA_H - 34), "NEURAL STREAM ENCRYPTION ACTIVE // HALL EFFECT RAPID TRIGGER 0.1mm // 8000Hz USB DIRECT", font=font_small, fill=(0, 200, 80))
    draw.text((SSAA_W - 220, SSAA_H - 34), "[WVGA 800x480]", font=font_small, fill=(180, 255, 200))

    # Downscale 2x SSAA -> 800x480 with Lanczos anti-aliasing
    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME 2: TOXIC RADAR (Apex Tactical Mech HUD & 360° Sonar)
# =============================================================================

def generate_toxic_radar() -> Image.Image:
    """
    Preset: Toxic Radar.
    Features: Ultra-tactical military/mech cockpit in toxic neon green (#39ff14),
    honeycomb carbon-fiber background, 360° circular sonar radar sweep with crosshairs,
    range rings, and target blips.
    """
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#080f0a")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 20)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 9)

    # 1. Honeycomb Carbon Lattice Background Texture
    for hy in range(0, SSAA_H, 40):
        for hx in range(0, SSAA_W, 46):
            offset_x = 23 if ((hy // 40) % 2 == 1) else 0
            px = hx + offset_x
            draw.regular_polygon((px, hy, 16), n_sides=6, rotation=30, outline=(14, 28, 18), fill=(8, 17, 11))

    # 2. Glowing 360° Tactical Sonar Radar in Center
    rcx, rcy = SSAA_W // 2, SSAA_H // 2 + 10

    # Glow under radar
    radar_glow = Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0))
    rg_draw = ImageDraw.Draw(radar_glow)
    rg_draw.ellipse([(rcx - 360, rcy - 360), (rcx + 360, rcy + 360)], fill=(0, 255, 65, 30))
    radar_glow = radar_glow.filter(ImageFilter.GaussianBlur(35))
    img.paste(Image.composite(radar_glow, Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0)), radar_glow), (0, 0), radar_glow)

    # Concentric Range Rings (100m, 500m, 1000m, 2000m)
    for rad, label in [(100, "100m"), (200, "500m"), (300, "1000m"), (400, "2000m")]:
        draw.ellipse([(rcx - rad, rcy - rad), (rcx + rad, rcy + rad)], outline=(0, 255, 65) if rad == 400 else (0, 160, 45), width=2 if rad < 400 else 4)
        draw.text((rcx + 8, rcy - rad - 20), label, font=font_small, fill=(0, 200, 55))

    # Compass Crosshairs & Degree Ticks
    draw.line([(rcx - 430, rcy), (rcx + 430, rcy)], fill=(0, 255, 65), width=2)
    draw.line([(rcx, rcy - 430), (rcx, rcy + 430)], fill=(0, 255, 65), width=2)

    # Compass Headings
    draw.text((rcx - 24, rcy - 440), "000° N", font=font_small, fill=(57, 255, 20))
    draw.text((rcx + 416, rcy - 12), "090° E", font=font_small, fill=(57, 255, 20))
    draw.text((rcx - 24, rcy + 416), "180° S", font=font_small, fill=(57, 255, 20))
    draw.text((rcx - 450, rcy - 12), "270° W", font=font_small, fill=(57, 255, 20))

    # Angle tick marks around perimeter
    for deg in range(0, 360, 15):
        rad = math.radians(deg)
        r1 = 390
        r2 = 410 if deg % 45 == 0 else 400
        x1 = rcx + r1 * math.cos(rad)
        y1 = rcy + r1 * math.sin(rad)
        x2 = rcx + r2 * math.cos(rad)
        y2 = rcy + r2 * math.sin(rad)
        draw.line([(x1, y1), (x2, y2)], fill=(57, 255, 20), width=2)

    # Radar Sweep Beam Wedge
    sweep = Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0))
    sw_draw = ImageDraw.Draw(sweep)
    sweep_start = 220
    for s_step in range(40):
        angle = sweep_start + s_step
        rad = math.radians(angle)
        alpha = int(120 * (s_step / 40.0))
        ex = rcx + 395 * math.cos(rad)
        ey = rcy + 395 * math.sin(rad)
        sw_draw.line([(rcx, rcy), (ex, ey)], fill=(57, 255, 20, alpha), width=3)
    img.paste(Image.composite(sweep, Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0)), sweep), (0, 0), sweep)

    # Target Blips / Pings
    targets = [
        (rcx + 140, rcy - 110, "TGT-01 [LOCKED]"),
        (rcx - 210, rcy + 130, "TGT-02 [CLEARED]"),
        (rcx + 260, rcy + 160, "SYS-BEACON"),
    ]
    for tx, ty, t_lbl in targets:
        draw.polygon([(tx, ty - 12), (tx + 12, ty), (tx, ty + 12), (tx - 12, ty)], fill=(57, 255, 20))
        draw.ellipse([(tx - 24, ty - 24), (tx + 24, ty + 24)], outline=(57, 255, 20), width=2)
        draw.text((tx + 20, ty - 10), t_lbl, font=font_small, fill=(210, 255, 200))

    # 3. Cockpit Angular Header & Framing
    draw.polygon([
        (0, 0), (SSAA_W, 0), (SSAA_W, 70),
        (SSAA_W - 100, 70), (SSAA_W - 140, 84),
        (140, 84), (100, 70), (0, 70)
    ], fill=(12, 28, 16))
    draw.line([(0, 70), (100, 70), (140, 84), (SSAA_W - 140, 84), (SSAA_W - 100, 70), (SSAA_W, 70)], fill=(57, 255, 20), width=4)

    draw.text((45, 18), "TURTLE BEACH", font=font_bold, fill=(57, 255, 20))
    draw.text((250, 14), "// APEX TOXIC CORE HUD [TACTICAL COMMAND]", font=font_title, fill="#ffffff")
    draw.text((SSAA_W - 280, 24), "[DEFENSE: ACTIVE]", font=font_small, fill=(57, 255, 20))

    # 4. Bottom Mech Telemetry Footer
    draw.rectangle([(0, SSAA_H - 42), (SSAA_W, SSAA_H)], fill=(10, 24, 14))
    draw.line([(0, SSAA_H - 42), (SSAA_W, SSAA_H - 42)], fill=(57, 255, 20), width=2)
    draw.text((40, SSAA_H - 32), "RAPID TRIGGER: ACTIVE [0.1mm] // HALL-EFFECT MAGNETIC CORE // SCAN: 8000Hz // THREAT LEVEL: ZERO", font=font_small, fill=(57, 255, 20))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME 3: BIOHAZARD REACTOR (Quantum Fusion Core & Radiant Plasma Glow)
# =============================================================================

def generate_biohazard_reactor() -> Image.Image:
    """
    Preset: Biohazard Reactor.
    Features: Nuclear emerald plasma (#00ff88) fusion reactor core, dark brushed titanium,
    circular magnetic containment ring with 8 radial plasma emitter spokes,
    horizontal and vertical luminous circuit busways.
    """
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#050a06")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 20)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 9)

    # 1. Dark Brushed Metal Texture
    for y in range(0, SSAA_H, 2):
        shade = int(5 + 5 * math.sin(y * 0.05))
        draw.line([(0, y), (SSAA_W, y)], fill=(shade, shade + 5, shade + 3))

    # 2. Glowing Plasma Conduits & Circuit Traces (Horizontal & Vertical Busways)
    conduits = [
        # Horizontal power lines
        [(0, 240), (SSAA_W, 240)],
        [(0, 720), (SSAA_W, 720)],
        [(100, 480), (SSAA_W - 100, 480)],
        # Vertical busways
        [(360, 80), (360, SSAA_H - 40)],
        [(SSAA_W - 360, 80), (SSAA_W - 360, SSAA_H - 40)],
    ]
    for p1, p2 in conduits:
        draw.line([p1, p2], fill=(0, 65, 30), width=6)
        draw.line([p1, p2], fill=(0, 180, 80), width=2)

    # 3. Center Plasma Fusion Core & Containment Chamber
    cx, cy = SSAA_W // 2, SSAA_H // 2

    # Volumetric Radiant Emerald Bloom
    plasma_bloom = Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0))
    pb_draw = ImageDraw.Draw(plasma_bloom)
    for r in range(320, 0, -25):
        alpha = int(40 * (1.0 - r / 320.0))
        pb_draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(0, 255, 136, alpha))
    plasma_bloom = plasma_bloom.filter(ImageFilter.GaussianBlur(30))
    img.paste(Image.composite(plasma_bloom, Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0)), plasma_bloom), (0, 0), plasma_bloom)

    # Industrial Magnetic Containment Ring
    draw.ellipse([(cx - 240, cy - 240), (cx + 240, cy + 240)], outline=(0, 255, 136), width=6)
    draw.ellipse([(cx - 200, cy - 200), (cx + 200, cy + 200)], outline=(0, 180, 90), width=2)
    draw.ellipse([(cx - 140, cy - 140), (cx + 140, cy + 140)], fill=(8, 28, 16), outline=(0, 255, 136), width=4)

    # 8 Radial Plasma Emitter Spokes
    for i in range(8):
        deg = i * 45
        rad = math.radians(deg)
        x1 = cx + 80 * math.cos(rad)
        y1 = cy + 80 * math.sin(rad)
        x2 = cx + 240 * math.cos(rad)
        y2 = cy + 240 * math.sin(rad)
        draw.line([(x1, y1), (x2, y2)], fill=(0, 255, 136), width=6)
        draw.line([(x1, y1), (x2, y2)], fill=(220, 255, 235), width=2)

    # Central Fusion Core Rune
    draw.ellipse([(cx - 60, cy - 60), (cx + 60, cy + 60)], fill=(0, 255, 136))
    draw.ellipse([(cx - 35, cy - 35), (cx + 35, cy + 35)], fill=(235, 255, 245))

    # Core Decals & Warning Labels
    draw.text((cx - 130, cy - 280), "CAUTION: HIGH VOLTAGE PLASMA", font=font_small, fill=(0, 255, 136))
    draw.text((cx - 105, cy + 260), "[OUTPUT: 1.21 GW NOMINAL]", font=font_small, fill=(0, 255, 136))

    # 4. Industrial Framing & Header
    draw.polygon([
        (0, 0), (SSAA_W, 0), (SSAA_W, 68),
        (SSAA_W - 90, 68), (SSAA_W - 130, 82),
        (130, 82), (90, 68), (0, 68)
    ], fill=(12, 28, 16))
    draw.line([(0, 68), (90, 68), (130, 82), (SSAA_W - 130, 82), (SSAA_W - 90, 68), (SSAA_W, 68)], fill=(0, 255, 136), width=4)

    draw.text((45, 18), "TURTLE BEACH", font=font_bold, fill=(0, 255, 136))
    draw.text((250, 14), "// ☣ QUANTUM BIO-REACTOR CORE [STATUS: NOMINAL]", font=font_title, fill="#ffffff")
    draw.text((SSAA_W - 290, 24), "CONTAINMENT: 99.8%", font=font_small, fill=(0, 255, 136))

    # 5. Bottom Status Bar
    draw.rectangle([(0, SSAA_H - 42), (SSAA_W, SSAA_H)], fill=(10, 22, 14))
    draw.line([(0, SSAA_H - 42), (SSAA_W, SSAA_H - 42)], fill=(0, 255, 136), width=2)
    draw.text((40, SSAA_H - 32), "THERMAL RUNAWAY PROTECTION: ENGAGED // EMERALD FLUX STABILIZER // DUAL SONIX/ARTERY MCU LINK", font=font_small, fill=(0, 220, 110))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME 4: EMERALD SYNTHWAVE (Retro Wireframe Grid & Rising Neon Sun)
# =============================================================================

def generate_emerald_synthwave() -> Image.Image:
    """
    Preset: Emerald Synthwave.
    Features: 3D perspective wireframe grid in electric emerald neon, glowing wireframe
    horizon, digital sliced neon sun, star dust, and retro-futuristic synthwave vibe.
    """
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#030805")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 20)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 9)

    horizon = 500
    vanishing_x = SSAA_W // 2

    # 1. Emerald Space Gradient
    for y in range(horizon):
        ratio = y / horizon
        r = int(2 + 10 * ratio)
        g = int(8 + 35 * ratio)
        b = int(4 + 18 * ratio)
        draw.line([(0, y), (SSAA_W, y)], fill=(r, g, b))

    # 2. Digital Wireframe Sun on Horizon
    sun_cx, sun_cy, sun_r = vanishing_x, horizon - 20, 160

    # Sun ambient glow
    sun_glow = Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0))
    sg_draw = ImageDraw.Draw(sun_glow)
    sg_draw.ellipse([(sun_cx - 220, sun_cy - 220), (sun_cx + 220, sun_cy + 220)], fill=(0, 255, 136, 45))
    sun_glow = sun_glow.filter(ImageFilter.GaussianBlur(35))
    img.paste(Image.composite(sun_glow, Image.new("RGBA", (SSAA_W, SSAA_H), (0, 0, 0, 0)), sun_glow), (0, 0), sun_glow)

    # Sun disk with horizontal synthwave blinds/slits
    draw.ellipse([(sun_cx - sun_r, sun_cy - sun_r), (sun_cx + sun_r, sun_cy + sun_r)], fill=(0, 255, 120))
    # Slicing lines with increasing thickness towards bottom
    y_slit = sun_cy - 40
    slit_h = 4
    while y_slit < sun_cy + sun_r:
        draw.rectangle([(sun_cx - sun_r - 10, int(y_slit)), (sun_cx + sun_r + 10, int(y_slit + slit_h))], fill=(4, 18, 9))
        slit_h *= 1.45
        y_slit += slit_h + 8

    # 3. 3D Perspective Floor Grid
    # Perspective rays from vanishing point
    for x in range(-400, SSAA_W + 500, 100):
        draw.line([(vanishing_x, horizon), (x, SSAA_H)], fill=(0, 255, 120), width=2)

    # Horizontal grid lines with perspective spacing
    y_step = horizon
    spacing = 10
    while y_step < SSAA_H:
        draw.line([(0, int(y_step)), (SSAA_W, int(y_step))], fill=(0, 255, 120), width=2)
        spacing *= 1.34
        y_step += spacing

    # Horizon Neon Beam
    draw.line([(0, horizon), (SSAA_W, horizon)], fill=(180, 255, 210), width=4)

    # 4. Top Glowing Banner
    draw.rectangle([(0, 0), (SSAA_W, 76)], fill=(10, 24, 14))
    draw.line([(0, 76), (SSAA_W, 76)], fill=(0, 255, 120), width=4)
    draw.line([(0, 80), (SSAA_W, 80)], fill=(0, 180, 85), width=2)

    draw.text((50, 22), "TURTLE BEACH // コマンド KB7", font=font_bold, fill=(0, 255, 120))
    draw.text((SSAA_W // 2 - 200, 18), "EMERALD SYNTHWAVE // RETRO HUD", font=font_title, fill="#ffffff")
    draw.text((SSAA_W - 250, 26), "[GRID: LOCKED]", font=font_small, fill=(0, 255, 120))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME 5: TACTICAL HUD (Cyan & Amber Cockpit Telemetry - Upgraded SSAA)
# =============================================================================

def generate_tactical_hud() -> Image.Image:
    """Preset: Tactical HUD Cockpit (Cyan & Amber) with full 2x SSAA anti-aliasing."""
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#080c14")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 20)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 9)

    # Gradient background
    for y in range(SSAA_H):
        ratio = y / SSAA_H
        r = int(8 + 8 * math.sin(ratio * math.pi))
        g = int(12 + 10 * ratio)
        b = int(20 + 25 * ratio)
        draw.line([(0, y), (SSAA_W, y)], fill=(r, g, b))

    # Tech Matrix Grid
    for x in range(0, SSAA_W, 80):
        draw.line([(x, 80), (x, SSAA_H - 50)], fill=(0, 35, 55), width=2)
    for y in range(80, SSAA_H - 50, 80):
        draw.line([(0, y), (SSAA_W, y)], fill=(0, 35, 55), width=2)

    # Top Header Telemetry Bar
    draw.polygon([
        (0, 0), (SSAA_W, 0), (SSAA_W, 72),
        (SSAA_W - 80, 72), (SSAA_W - 120, 84),
        (120, 84), (80, 72), (0, 72)
    ], fill=(12, 22, 36))
    draw.line([(0, 72), (80, 72), (120, 84), (SSAA_W - 120, 84), (SSAA_W - 80, 72), (SSAA_W, 72)], fill=(0, 229, 255), width=4)

    draw.text((50, 20), "TURTLE BEACH", font=font_bold, fill=(255, 179, 0))
    draw.text((250, 16), "// COMMAND KB7 TACTICAL HUD", font=font_title, fill=(0, 229, 255))
    draw.text((SSAA_W - 250, 24), "ONLINE // 8000Hz", font=font_small, fill=(0, 230, 118))

    # Center Equalizer Bars
    for i in range(32):
        h = int(24 + 20 * math.sin(i * 0.4) * math.cos(i * 0.2))
        bx = 660 + i * 10
        by = 480 - h // 2
        color = (0, 229, 255) if i < 22 else (255, 179, 0)
        draw.line([(bx, by), (bx, by + h)], fill=color, width=4)

    # Bottom Status Bar
    draw.rectangle([(0, SSAA_H - 44), (SSAA_W, SSAA_H)], fill=(10, 16, 26))
    draw.line([(0, SSAA_H - 44), (SSAA_W, SSAA_H - 44)], fill=(0, 150, 180), width=2)
    draw.text((40, SSAA_H - 34), "DUAL-MCU ARCHITECTURE [SONIX + ARTERY] // RAPID TRIGGER READY", font=font_small, fill=(100, 140, 180))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME 6: AUDIOPHILE DARK (Studio Console & Golden VU Meters - Upgraded SSAA)
# =============================================================================

def generate_audiophile_dark() -> Image.Image:
    """Preset: Audiophile Dark Studio Console with golden VU meters and SSAA."""
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#0f1115")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 18)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 9)

    # Brushed Chassis
    for y in range(SSAA_H):
        shade = int(14 + 6 * math.sin(y * 0.05) + 4 * (y / SSAA_H))
        draw.line([(0, y), (SSAA_W, y)], fill=(shade, shade + 2, shade + 4))

    # Golden Header
    draw.rectangle([(0, 0), (SSAA_W, 72)], fill=(22, 25, 32))
    draw.line([(0, 72), (SSAA_W, 72)], fill=(230, 165, 30), width=4)
    draw.text((50, 18), "TURTLE BEACH", font=font_bold, fill=(230, 165, 30))
    draw.text((250, 16), "COMMAND SERIES // MASTER AUDIO CONSOLE", font=font_title, fill="#ffffff")

    # Dual Analog VU Meters
    vu_boxes = [(200, 110, 540, 280, "CHANNEL A // MASTER L"), (860, 110, 540, 280, "CHANNEL B // MASTER R")]
    for vx, vy, vw, vh, title in vu_boxes:
        draw.rectangle([(vx, vy), (vx + vw, vy + vh)], fill=(24, 28, 36), outline=(60, 68, 85), width=4)
        draw.rectangle([(vx + 20, vy + 20), (vx + vw - 20, vy + vh - 50)], fill=(32, 38, 48))
        draw.text((vx + 32, vy + vh - 40), title, font=font_small, fill=(200, 160, 60))

        # Golden needle
        cx, cy = vx + vw // 2, vy + vh - 20
        rad = math.radians(275)
        nx = cx + 160 * math.cos(rad)
        ny = cy + 160 * math.sin(rad)
        draw.line([(cx, cy), (nx, ny)], fill=(255, 190, 40), width=6)
        draw.ellipse([(cx - 12, cy - 12), (cx + 12, cy + 12)], fill=(255, 190, 40))

    # Bottom status bar
    draw.rectangle([(0, SSAA_H - 40), (SSAA_W, SSAA_H)], fill=(16, 18, 24))
    draw.line([(0, SSAA_H - 40), (SSAA_W, SSAA_H - 40)], fill=(230, 165, 30), width=2)
    draw.text((50, SSAA_H - 32), "STUDIO HIGH-DEFINITION SOUND INTERFACE // HARDWARE ROTARY DIAL SYNC", font=font_small, fill=(180, 180, 180))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME 7: NEON CYBERPUNK (Synthwave Electric Magenta & Cyan - Upgraded SSAA)
# =============================================================================

def generate_neon_cyberpunk() -> Image.Image:
    """Preset: Neon Cyberpunk Synthwave with electric magenta/cyan horizon and SSAA."""
    img = Image.new("RGB", (SSAA_W, SSAA_H), "#0a0614")
    draw = ImageDraw.Draw(img)

    font_title = _get_font("bahnschrift.ttf", 22)
    font_bold = _get_font("bahnschrift.ttf", 13)
    font_small = _get_font("consolab.ttf", 9)

    # Sunset Gradient
    for y in range(SSAA_H):
        ratio = y / SSAA_H
        r = int(15 + 40 * ratio)
        g = int(8 + 10 * ratio)
        b = int(35 + 45 * ratio)
        draw.line([(0, y), (SSAA_W, y)], fill=(r, g, b))

    # Perspective Grid
    horizon = 520
    vanishing_x = SSAA_W // 2
    for x in range(-400, SSAA_W + 500, 100):
        draw.line([(vanishing_x, horizon), (x, SSAA_H)], fill=(255, 0, 128), width=2)
    y_step = horizon
    spacing = 10
    while y_step < SSAA_H:
        draw.line([(0, int(y_step)), (SSAA_W, int(y_step))], fill=(0, 240, 255), width=2)
        spacing *= 1.35
        y_step += spacing

    # Top Banner
    draw.rectangle([(0, 0), (SSAA_W, 80)], fill=(18, 12, 32))
    draw.line([(0, 80), (SSAA_W, 80)], fill=(255, 0, 128), width=4)
    draw.line([(0, 84), (SSAA_W, 84)], fill=(0, 240, 255), width=2)

    draw.text((50, 22), "TURTLE BEACH // コマンド KB7", font=font_bold, fill=(255, 0, 128))
    draw.text((SSAA_W // 2 - 180, 16), "CYBERDECK HUD v2.5", font=font_title, fill=(0, 240, 255))

    return img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


# =============================================================================
# THEME CATALOG & PRESETS
# =============================================================================

THEME_PRESETS: Dict[str, Callable[[], Image.Image]] = {
    # New Green Themes
    "matrix_cyberdeck": generate_matrix_cyberdeck,
    "toxic_radar": generate_toxic_radar,
    "biohazard_reactor": generate_biohazard_reactor,
    "emerald_synthwave": generate_emerald_synthwave,
    # Classic Upgraded Themes
    "tactical_hud": generate_tactical_hud,
    "audiophile_dark": generate_audiophile_dark,
    "neon_cyberpunk": generate_neon_cyberpunk,
}


def build_and_save_themes(output_dir: str) -> dict:
    """Builds all themes and saves them as PNG images in output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    for name, gen_fn in THEME_PRESETS.items():
        img = gen_fn()
        path = os.path.join(output_dir, f"{name}.png")
        img.save(path)
        paths[name] = path
    return paths
