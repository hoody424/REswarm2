"""
Image conversion utilities for the Turtle Beach Command Series KB7 display.

Grounded in disassembly of COMMAND_KB7.dll:
- SetBg (0x0029D5C0):
  - Slot 0x00 (Full Wallpaper): scales with Qt::KeepAspectRatioByExpanding to cover
    480x800 (width=480, height=800), center-crops to 480x800, and converts via
    LvglImageConverter (0x0023CE40 -> 0x0023C110) in Mode 0 (RGB565 Little-Endian,
    2 bytes/pixel = 768,000 bytes).
  - Slot 0x40 (Thumbnail): scales to 148x148, center-crops to 142x148 (width=142,
    height=148), and converts via LvglImageConverter in Mode 1 (RGB565 Little-Endian
    42,032 bytes + 8-bit Alpha plane 21,016 bytes = 63,048 bytes total).
"""

from pathlib import Path
from typing import Union
from PIL import Image

LCD_WIDTH = 480
LCD_HEIGHT = 800
THUMB_WIDTH = 142
THUMB_HEIGHT = 148

# 4x4 Bayer matrix normalized to [-0.5, +0.4375] for smooth RGB565 quantization
_BAYER_4X4 = (
    (-8 / 16.0,  0 / 16.0, -6 / 16.0,  2 / 16.0),
    ( 4 / 16.0, -4 / 16.0,  6 / 16.0, -2 / 16.0),
    (-5 / 16.0,  3 / 16.0, -7 / 16.0,  1 / 16.0),
    ( 7 / 16.0, -1 / 16.0,  5 / 16.0, -3 / 16.0),
)


def scale_and_center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Replicates Qt's QImage::scaled(target_w, target_h, Qt::KeepAspectRatioByExpanding,
    Qt::SmoothTransformation) followed by center QImage::copy((w-target_w)//2, (h-target_h)//2).
    """
    src_w, src_h = img.size
    if (src_w, src_h) == (target_w, target_h):
        return img

    scale = max(target_w / max(1, src_w), target_h / max(1, src_h))
    scaled_w = max(target_w, int(round(src_w * scale)))
    scaled_h = max(target_h, int(round(src_h * scale)))

    resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    if (scaled_w, scaled_h) == (target_w, target_h):
        return resized

    left = (scaled_w - target_w) // 2
    top = (scaled_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def convert_to_rgb565(
    image_source: Union[str, Path, Image.Image],
    width: int = LCD_WIDTH,
    height: int = LCD_HEIGHT,
    byte_order: str = "little",
    dither: bool = True,
    crop_cover: bool = True,
    include_alpha: bool = False,
) -> bytes:
    """
    Convert an image file or PIL Image into raw 16-bit RGB565 bytes for the KB7 LCD.

    Parameters
    ----------
    image_source : str | Path | PIL.Image.Image
        Path to an image file or an already-loaded PIL Image object.
    width : int
        Target width in pixels (default: 480 for Slot 0x00, 142 for Slot 0x40).
    height : int
        Target height in pixels (default: 800 for Slot 0x00, 148 for Slot 0x40).
    byte_order : str
        "little" (default, matching LvglImageConverter 0x0023C110) or "big".
    dither : bool
        Apply 4x4 Bayer ordered dithering to eliminate RGB565 gradient banding.
    crop_cover : bool
        Use aspect-preserving scale + center crop (matching SetBg in COMMAND_KB7.dll).
    include_alpha : bool
        Append 1-byte-per-pixel alpha plane after RGB565 data (Mode 1 in
        LvglImageConverter, required for Slot 0x40 where total size is 3 * W * H).

    Returns
    -------
    bytes
        Raw pixel buffer of length `width * height * 2` (or `width * height * 3`
        when `include_alpha=True`).
    """
    if isinstance(image_source, (str, Path)):
        img = Image.open(image_source)
    elif isinstance(image_source, Image.Image):
        img = image_source.copy()
    else:
        raise TypeError(f"Unsupported image_source type: {type(image_source)}")

    if crop_cover:
        img = scale_and_center_crop(img, width, height)
    elif img.size != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)

    alpha_plane = b""
    if include_alpha:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            alpha_plane = rgba.getchannel("A").tobytes()
        else:
            alpha_plane = b"\xff" * (width * height)

    img = img.convert("RGB")
    raw_rgb = img.tobytes()

    out = bytearray(width * height * 2)
    little = (byte_order == "little")

    if dither:
        idx = 0
        out_idx = 0
        for y in range(height):
            bayer_row = _BAYER_4X4[y & 3]
            for x in range(width):
                b_val = bayer_row[x & 3]
                # R and B have step size 8 (8-bit -> 5-bit); G has step size 4 (8-bit -> 6-bit)
                r = int(raw_rgb[idx] + b_val * 8.0)
                g = int(raw_rgb[idx + 1] + b_val * 4.0)
                b = int(raw_rgb[idx + 2] + b_val * 8.0)
                if r < 0:
                    r = 0
                elif r > 255:
                    r = 255
                if g < 0:
                    g = 0
                elif g > 255:
                    g = 255
                if b < 0:
                    b = 0
                elif b > 255:
                    b = 255

                rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                if little:
                    out[out_idx] = rgb565 & 0xFF
                    out[out_idx + 1] = (rgb565 >> 8) & 0xFF
                else:
                    out[out_idx] = (rgb565 >> 8) & 0xFF
                    out[out_idx + 1] = rgb565 & 0xFF
                idx += 3
                out_idx += 2
    else:
        out_idx = 0
        for i in range(0, len(raw_rgb), 3):
            r = raw_rgb[i]
            g = raw_rgb[i + 1]
            b = raw_rgb[i + 2]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            if little:
                out[out_idx] = rgb565 & 0xFF
                out[out_idx + 1] = (rgb565 >> 8) & 0xFF
            else:
                out[out_idx] = (rgb565 >> 8) & 0xFF
                out[out_idx + 1] = rgb565 & 0xFF
            out_idx += 2

    if include_alpha:
        return bytes(out) + alpha_plane
    return bytes(out)


def create_test_pattern(width: int = LCD_WIDTH, height: int = LCD_HEIGHT) -> Image.Image:
    """Create a 480x800 test pattern image."""
    from .theme_generator import generate_theme
    im = generate_theme("emerald_synthwave")
    if im.size != (width, height):
        im = im.resize((width, height), Image.Resampling.LANCZOS)
    return im

