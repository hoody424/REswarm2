"""
Procedural 480x800 LCD Theme Generator for the Turtle Beach Command Series KB7.

Grounded in COMMAND_KB7.dll SetBg (0x0029D5C0) and default_1.png (1920x3200 = 4x 480x800):
The KB7 wallpaper framebuffer (Slot 0x00) has row stride width=480 and height=800.
All themes are rendered at 2x Supersampling (960x1600) and downsampled with LANCZOS
to 480x800 so circles, grids, and typography have zero stride wrapping and razor-sharp edges.
"""

import math
import random
from PIL import Image, ImageDraw, ImageFilter

from .image import LCD_WIDTH, LCD_HEIGHT

SSAA = 2


def generate_theme(
    name: str = "emerald_synthwave",
    width: int = LCD_WIDTH,
    height: int = LCD_HEIGHT,
) -> Image.Image:
    """
    Generate a procedural wallpaper image (default: 480x800 for KB7 Slot 0x00).

    Available themes:
    - "emerald_synthwave" : Neon Emerald Outrun Sun & Perspective Grid
    - "matrix_cyberdeck"  : Digital Matrix Rain & Emerald HUD
    - "toxic_radar"       : Military Sonar Sweep & Phosphor Green Grid
    - "biohazard_reactor" : Glowing Emerald Core & Hexagonal Containment
    - "cyberpunk_grid"    : Neon Outrun / Synthwave Horizon
    - "telemetry_hud"     : Sci-Fi Tactical Command HUD
    - "stealth_carbon"    : Dark Brushed Carbon + Cyan/Violet Edge Glow
    - "supernova_core"    : Deep Space Plasma / Energy Core
    """
    rw, rh = width * SSAA, height * SSAA
    if name == "emerald_synthwave":
        hi = _render_emerald_synthwave(rw, rh)
    elif name == "matrix_cyberdeck":
        hi = _render_matrix_cyberdeck(rw, rh)
    elif name == "toxic_radar":
        hi = _render_toxic_radar(rw, rh)
    elif name == "biohazard_reactor":
        hi = _render_biohazard_reactor(rw, rh)
    elif name == "cyberpunk_grid":
        hi = _render_cyberpunk_grid(rw, rh)
    elif name in ("telemetry_hud", "tactical_hud"):
        hi = _render_telemetry_hud(rw, rh)
    elif name in ("stealth_carbon", "audiophile_dark"):
        hi = _render_stealth_carbon(rw, rh)
    elif name in ("supernova_core", "neon_cyberpunk"):
        hi = _render_supernova_core(rw, rh)
    elif name == "minecraft_hud":
        from .minecraft import render_minecraft_hud_canvas
        return render_minecraft_hud_canvas(None, width=width, height=height)
    else:
        raise ValueError(f"Unknown theme name: {name}")

    return hi.resize((width, height), Image.Resampling.LANCZOS)


THEME_PRESETS = {
    "minecraft_hud": lambda: generate_theme("minecraft_hud"),
    "emerald_synthwave": lambda: generate_theme("emerald_synthwave"),
    "matrix_cyberdeck": lambda: generate_theme("matrix_cyberdeck"),
    "toxic_radar": lambda: generate_theme("toxic_radar"),
    "biohazard_reactor": lambda: generate_theme("biohazard_reactor"),
    "cyberpunk_grid": lambda: generate_theme("cyberpunk_grid"),
    "telemetry_hud": lambda: generate_theme("telemetry_hud"),
    "tactical_hud": lambda: generate_theme("tactical_hud"),
    "stealth_carbon": lambda: generate_theme("stealth_carbon"),
    "audiophile_dark": lambda: generate_theme("audiophile_dark"),
    "supernova_core": lambda: generate_theme("supernova_core"),
    "neon_cyberpunk": lambda: generate_theme("neon_cyberpunk"),
}


def _render_emerald_synthwave(w: int, h: int) -> Image.Image:
    """Neon Emerald Outrun Sun & Perspective Grid (Green Synthwave)."""
    img = Image.new("RGB", (w, h), (2, 10, 6))
    draw = ImageDraw.Draw(img)

    horizon_y = int(h * 0.54)
    # Deep forest-to-emerald sky gradient
    for y in range(horizon_y):
        t = y / max(1, horizon_y)
        r = int(2 + 12 * (t ** 2))
        g = int(10 + 95 * (t ** 1.6))
        b = int(8 + 45 * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Ground base gradient
    for y in range(horizon_y, h):
        t = (y - horizon_y) / max(1, h - horizon_y)
        r = int(6 * (1 - t))
        g = int(38 * (1 - t) + 8)
        b = int(20 * (1 - t) + 4)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Single centered glowing emerald/lime sun with synthwave horizontal slice bars
    sun_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sun_layer)
    sun_r = int(min(w, h) * 0.28)
    cx, cy = w // 2, horizon_y - int(sun_r * 0.18)

    # Outer atmospheric halo
    halo_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(halo_layer)
    hdraw.ellipse(
        [cx - int(sun_r * 1.35), cy - int(sun_r * 1.35), cx + int(sun_r * 1.35), cy + int(sun_r * 1.35)],
        fill=(0, 255, 128, 70),
    )
    halo_layer = halo_layer.filter(ImageFilter.GaussianBlur(radius=28))
    img = Image.alpha_composite(img.convert("RGBA"), halo_layer).convert("RGB")

    for dy in range(-sun_r, sun_r):
        y = cy + dy
        if y >= horizon_y:
            continue
        norm_y = (dy + sun_r) / (2 * sun_r)
        if norm_y > 0.52 and (int(norm_y * 36) % 3 == 0):
            continue
        half_x = int(math.sqrt(max(0, sun_r * sun_r - dy * dy)))
        r = int(30 + 170 * (1 - norm_y))
        g = 255
        b = int(110 + 110 * norm_y)
        sdraw.line([(cx - half_x, y), (cx + half_x, y)], fill=(r, g, b, 245))

    img = Image.alpha_composite(img.convert("RGBA"), sun_layer).convert("RGB")

    # Perspective grid with bloom
    grid_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid_layer)

    for i in range(-16, 17):
        top_x = cx + i * int(w * 0.025)
        bot_x = cx + i * int(w * 0.16)
        gdraw.line([(top_x, horizon_y), (bot_x, h)], fill=(0, 255, 136, 190), width=3)

    for i in range(1, 18):
        t = (i / 17.0) ** 2.1
        y = horizon_y + int(t * (h - horizon_y))
        alpha = int(90 + 165 * (i / 17.0))
        gdraw.line([(0, y), (w, y)], fill=(40, 255, 160, alpha), width=3)

    # Horizon laser beam
    gdraw.line([(0, horizon_y), (w, horizon_y)], fill=(180, 255, 220, 255), width=6)

    glow = grid_layer.filter(ImageFilter.GaussianBlur(radius=10))
    base_rgba = img.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, glow)
    base_rgba = Image.alpha_composite(base_rgba, grid_layer)
    return base_rgba.convert("RGB")


def _render_matrix_cyberdeck(w: int, h: int) -> Image.Image:
    """Digital Matrix Rain & Emerald HUD."""
    img = Image.new("RGB", (w, h), (2, 8, 4))
    draw = ImageDraw.Draw(img)

    cx, cy = w // 2, h // 2
    max_r = math.hypot(cx, cy)
    for y in range(0, h, 2):
        dy = abs(y - cy) / max(1, cy)
        g = int(18 * (1.0 - 0.6 * dy))
        draw.line([(0, y), (w, y)], fill=(2, g + 6, 4))

    rain_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(rain_layer)

    rng = random.Random(1337)
    col_w = 24
    num_cols = w // col_w

    for col in range(num_cols):
        x = col * col_w + 8
        num_streaks = rng.randint(1, 3)
        for _ in range(num_streaks):
            head_y = rng.randint(60, h - 40)
            length = rng.randint(140, 420)
            seg_h = 16
            steps = length // seg_h
            for s in range(steps):
                sy = head_y - s * seg_h
                if sy < 0 or sy >= h:
                    continue
                fade = 1.0 - (s / max(1, steps))
                if s == 0:
                    color = (210, 255, 220, 250)
                elif s < 3:
                    color = (50, 255, 110, int(230 * fade))
                else:
                    color = (0, int(210 * fade), int(65 * fade), int(190 * fade))

                glyph_type = (col * 7 + s * 13) % 4
                if glyph_type == 0:
                    rdraw.rectangle([x, sy, x + 10, sy + 10], outline=color, width=2)
                elif glyph_type == 1:
                    rdraw.line([(x, sy + 2), (x + 10, sy + 2)], fill=color, width=2)
                    rdraw.line([(x + 5, sy + 2), (x + 5, sy + 10)], fill=color, width=2)
                elif glyph_type == 2:
                    rdraw.line([(x, sy), (x + 10, sy + 10)], fill=color, width=2)
                    rdraw.line([(x + 10, sy), (x, sy + 10)], fill=color, width=2)
                else:
                    rdraw.rectangle([x + 2, sy + 2, x + 8, sy + 8], fill=color)

    # Central Emerald Cyberdeck Frame
    hud_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hud_layer)
    m = 36
    b_len = 80
    bright_green = (0, 255, 110, 235)
    for bx, by, sx, sy in [(m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        hdraw.line([(bx, by), (bx + sx * b_len, by)], fill=bright_green, width=5)
        hdraw.line([(bx, by), (bx, by + sy * b_len)], fill=bright_green, width=5)

    ring_r = int(min(w, h) * 0.25)
    hdraw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r], outline=(0, 255, 100, 140), width=3)
    for a in range(0, 360, 45):
        hdraw.arc(
            [cx - ring_r - 18, cy - ring_r - 18, cx + ring_r + 18, cy + ring_r + 18],
            start=a,
            end=a + 22,
            fill=(80, 255, 150, 220),
            width=6,
        )

    rain_glow = rain_layer.filter(ImageFilter.GaussianBlur(radius=8))
    hud_glow = hud_layer.filter(ImageFilter.GaussianBlur(radius=10))
    base = img.convert("RGBA")
    base = Image.alpha_composite(base, rain_glow)
    base = Image.alpha_composite(base, rain_layer)
    base = Image.alpha_composite(base, hud_glow)
    base = Image.alpha_composite(base, hud_layer)
    return base.convert("RGB")


def _render_toxic_radar(w: int, h: int) -> Image.Image:
    """Military Sonar Sweep & Phosphor Green Grid."""
    img = Image.new("RGB", (w, h), (3, 12, 6))
    draw = ImageDraw.Draw(img)

    step = 48
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(6, 30, 14), width=2)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(6, 30, 14), width=2)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    cx, cy = w // 2, h // 2
    max_r = int(min(w, h) * 0.42)

    sweep_deg = 38.0
    trail_span = 75.0
    for i in range(int(trail_span * 2)):
        ang = sweep_deg - i * 0.5
        alpha = int(130 * ((1.0 - i / (trail_span * 2)) ** 1.8))
        odraw.pieslice(
            [cx - max_r, cy - max_r, cx + max_r, cy + max_r],
            start=ang - 0.6,
            end=ang + 0.6,
            fill=(20, 255, 90, alpha),
        )

    rad = math.radians(sweep_deg)
    odraw.line(
        [(cx, cy), (cx + int(max_r * math.cos(rad)), cy + int(max_r * math.sin(rad)))],
        fill=(180, 255, 200, 255),
        width=5,
    )

    for frac in (0.25, 0.5, 0.75, 1.0):
        r = int(max_r * frac)
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 240, 90, 190), width=3)

    for deg in range(0, 360, 5):
        a = math.radians(deg)
        inner = max_r + (4 if deg % 30 else 0)
        outer = max_r + (12 if deg % 30 else 22)
        col = (100, 255, 140, 230) if deg % 30 == 0 else (0, 200, 80, 140)
        odraw.line(
            [
                (cx + int(inner * math.cos(a)), cy + int(inner * math.sin(a))),
                (cx + int(outer * math.cos(a)), cy + int(outer * math.sin(a))),
            ],
            fill=col,
            width=3 if deg % 30 == 0 else 2,
        )

    odraw.line([(cx - max_r - 35, cy), (cx + max_r + 35, cy)], fill=(0, 220, 90, 130), width=2)
    odraw.line([(cx, cy - max_r - 35), (cx, cy + max_r + 35)], fill=(0, 220, 90, 130), width=2)

    for bx, by, br in [
        (cx + int(max_r * 0.42), cy + int(max_r * 0.25), 10),
        (cx - int(max_r * 0.50), cy - int(max_r * 0.30), 8),
        (cx + int(max_r * 0.18), cy - int(max_r * 0.60), 9),
    ]:
        odraw.ellipse([bx - br, by - br, bx + br, by + br], fill=(190, 255, 200, 255))
        odraw.ellipse([bx - br * 2, by - br * 2, bx + br * 2, by + br * 2], outline=(0, 255, 100, 180), width=3)

    glow = overlay.filter(ImageFilter.GaussianBlur(radius=9))
    base = img.convert("RGBA")
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, overlay)
    return base.convert("RGB")


def _render_biohazard_reactor(w: int, h: int) -> Image.Image:
    """Glowing Emerald Core & Hexagonal Containment."""
    img = Image.new("RGB", (w, h), (3, 10, 6))
    draw = ImageDraw.Draw(img)

    cx, cy = w // 2, h // 2
    hex_r = 46
    dx = int(hex_r * 1.5)
    dy = int(hex_r * math.sqrt(3))

    for col in range(-1, w // dx + 2):
        for row in range(-1, h // dy + 2):
            hx = col * dx
            hy = row * dy + (dy // 2 if col % 2 else 0)
            dist = math.hypot(hx - cx, hy - cy) / (min(w, h) * 0.65)
            intensity = max(0.0, 1.0 - dist * 0.85)
            g_col = int(18 + 55 * intensity)
            pts = []
            for i in range(6):
                ang = math.radians(60 * i)
                pts.append((hx + int((hex_r - 3) * math.cos(ang)), hy + int((hex_r - 3) * math.sin(ang))))
            draw.polygon(pts, outline=(4, g_col, int(g_col * 0.45)), width=2)

    core = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(core)
    base_r = int(min(w, h) * 0.36)

    for r in range(base_r, 10, -6):
        t = 1.0 - (r / float(base_r))
        alpha = int(18 * (t ** 1.5))
        cdraw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(int(40 * t), int(200 + 55 * t), int(80 * t), alpha),
        )

    ring1 = int(min(w, h) * 0.28)
    ring2 = int(min(w, h) * 0.20)
    ring3 = int(min(w, h) * 0.11)
    for a in range(0, 360, 60):
        cdraw.arc(
            [cx - ring1, cy - ring1, cx + ring1, cy + ring1],
            start=a + 6,
            end=a + 48,
            fill=(0, 255, 110, 230),
            width=10,
        )
    for a in range(0, 360, 120):
        cdraw.arc(
            [cx - ring2, cy - ring2, cx + ring2, cy + ring2],
            start=a + 15,
            end=a + 85,
            fill=(140, 255, 170, 245),
            width=14,
        )

    cdraw.ellipse(
        [cx - ring3, cy - ring3, cx + ring3, cy + ring3],
        fill=(190, 255, 210, 255),
        outline=(0, 255, 120, 255),
        width=6,
    )

    glow = core.filter(ImageFilter.GaussianBlur(radius=14))
    base = img.convert("RGBA")
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, core)
    return base.convert("RGB")


def _render_cyberpunk_grid(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), (8, 4, 20))
    draw = ImageDraw.Draw(img)

    horizon_y = int(h * 0.54)
    for y in range(horizon_y):
        t = y / max(1, horizon_y)
        r = int(8 + 90 * (t ** 1.8))
        g = int(4 + 18 * t)
        b = int(24 + 95 * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    for y in range(horizon_y, h):
        t = (y - horizon_y) / max(1, h - horizon_y)
        r = int(25 * (1 - t) + 6)
        g = int(6 * (1 - t) + 2)
        b = int(48 * (1 - t) + 16)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    sun_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(sun_layer)
    sun_r = int(min(w, h) * 0.28)
    cx, cy = w // 2, horizon_y - int(sun_r * 0.18)

    for dy in range(-sun_r, sun_r):
        y = cy + dy
        if y >= horizon_y:
            continue
        norm_y = (dy + sun_r) / (2 * sun_r)
        if norm_y > 0.55 and (int(norm_y * 40) % 3 == 0):
            continue
        half_x = int(math.sqrt(max(0, sun_r * sun_r - dy * dy)))
        r = 255
        g = int(220 * (1 - norm_y) + 20)
        b = int(40 + 180 * norm_y)
        sdraw.line([(cx - half_x, y), (cx + half_x, y)], fill=(r, g, b, 240))

    img = Image.alpha_composite(img.convert("RGBA"), sun_layer).convert("RGB")

    grid_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grid_layer)

    for i in range(-16, 17):
        top_x = cx + i * int(w * 0.025)
        bot_x = cx + i * int(w * 0.16)
        gdraw.line([(top_x, horizon_y), (bot_x, h)], fill=(0, 240, 255, 190), width=3)

    for i in range(1, 18):
        t = (i / 17.0) ** 2.2
        y = horizon_y + int(t * (h - horizon_y))
        alpha = int(80 + 175 * (i / 17.0))
        gdraw.line([(0, y), (w, y)], fill=(255, 0, 160, alpha), width=3)

    gdraw.line([(0, horizon_y), (w, horizon_y)], fill=(0, 255, 255, 255), width=6)

    glow = grid_layer.filter(ImageFilter.GaussianBlur(radius=9))
    base_rgba = img.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, glow)
    base_rgba = Image.alpha_composite(base_rgba, grid_layer)
    return base_rgba.convert("RGB")


def _render_telemetry_hud(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), (6, 12, 20))
    draw = ImageDraw.Draw(img)

    step = 48
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(12, 26, 42), width=2)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(12, 26, 42), width=2)

    hud = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hud)

    cx, cy = w // 2, h // 2
    cyan = (0, 229, 255, 220)
    amber = (255, 170, 0, 210)

    r_base = int(min(w, h) * 0.16)
    for idx, r in enumerate((r_base, int(r_base * 1.55), int(r_base * 2.1))):
        col = cyan if idx != 1 else amber
        hdraw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=3)

    r_arc = int(r_base * 1.8)
    for start_deg in range(0, 360, 60):
        hdraw.arc(
            [cx - r_arc, cy - r_arc, cx + r_arc, cy + r_arc],
            start=start_deg,
            end=start_deg + 35,
            fill=(0, 255, 200, 240),
            width=8,
        )

    span = int(min(w, h) * 0.42)
    hdraw.line([(cx - span, cy), (cx - int(r_base * 0.6), cy)], fill=cyan, width=3)
    hdraw.line([(cx + int(r_base * 0.6), cy), (cx + span, cy)], fill=cyan, width=3)
    hdraw.line([(cx, cy - span), (cx, cy - int(r_base * 0.6))], fill=cyan, width=3)
    hdraw.line([(cx, cy + int(r_base * 0.6)), (cx, cy + span)], fill=cyan, width=3)

    m = 36
    b_len = 80
    for bx, by, sx, sy in [(m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        hdraw.line([(bx, by), (bx + sx * b_len, by)], fill=amber, width=6)
        hdraw.line([(bx, by), (bx, by + sy * b_len)], fill=amber, width=6)

    glow = hud.filter(ImageFilter.GaussianBlur(radius=8))
    base = img.convert("RGBA")
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, hud)
    return base.convert("RGB")


def _render_stealth_carbon(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), (14, 15, 19))
    draw = ImageDraw.Draw(img)

    spacing = 24
    for offset in range(-h, w + h, spacing):
        draw.line([(offset, 0), (offset - h, h)], fill=(22, 24, 30), width=6)
        draw.line([(offset + 6, 0), (offset - h + 6, h)], fill=(10, 11, 14), width=4)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    odraw.rectangle([16, 16, w - 16, h - 16], outline=(0, 210, 255, 220), width=5)
    odraw.rectangle([32, 32, w - 32, h - 32], outline=(138, 43, 226, 180), width=3)

    cx, cy = w // 2, h // 2
    size = int(min(w, h) * 0.24)
    pts = [(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)]
    odraw.polygon(pts, outline=(0, 229, 255, 230), width=6)
    size2 = int(size * 0.68)
    pts2 = [(cx, cy - size2), (cx + size2, cy), (cx, cy + size2), (cx - size2, cy)]
    odraw.polygon(pts2, outline=(160, 60, 255, 200), width=4)

    glow = overlay.filter(ImageFilter.GaussianBlur(radius=12))
    base = img.convert("RGBA")
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, overlay)
    return base.convert("RGB")


def _render_supernova_core(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), (5, 2, 12))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    cx, cy = w // 2, h // 2
    max_r = int(min(w, h) * 0.44)
    for r in range(max_r, 8, -8):
        t = 1.0 - (r / float(max_r))
        red = int(40 + 215 * (t ** 1.3))
        green = int(10 + 180 * (t ** 2.4))
        blue = int(90 + 165 * (1 - abs(t - 0.5) * 2))
        alpha = int(22 * (t ** 1.2))
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(red, green, blue, alpha))

    ring_rx = int(min(w, h) * 0.38)
    ring_ry = int(min(w, h) * 0.16)
    for i in range(6):
        rx = ring_rx - i * 16
        ry = ring_ry - i * 6
        odraw.ellipse(
            [cx - rx, cy - ry, cx + rx, cy + ry],
            outline=(0, 220, 255, 160 - i * 20),
            width=4,
        )

    core_r = int(min(w, h) * 0.08)
    odraw.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r], fill=(255, 250, 240, 255))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=8))

    base = img.convert("RGBA")
    base = Image.alpha_composite(base, overlay)
    return base.convert("RGB")
