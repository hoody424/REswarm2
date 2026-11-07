"""
Image conversion utilities for Turtle Beach KB7 (800x480 RGB565 Little-Endian).
Features:
- High-quality Lanczos resampling
- 4x4 Bayer ordered dithering to eliminate color banding on gradients & dark backgrounds
- Fast branchless lookup-table RGB565 conversion
"""

from typing import Optional
import struct

# Standard 4x4 Bayer dithering matrix (values 0..15)
BAYER4 = (
    0, 8, 2, 10,
    12, 4, 14, 6,
    3, 11, 1, 9,
    15, 7, 13, 5
)

# Precalculate dithering tables for fast RGB565 conversion
# Red & Blue (5-bit, 32 levels, step=8): delta = (bayer - 7.5) * 0.5
# Green (6-bit, 64 levels, step=4):     delta = (bayer - 7.5) * 0.25
_DITHER_TABLE_R = bytearray(16 * 256)
_DITHER_TABLE_G = bytearray(16 * 256)
_DITHER_TABLE_B = bytearray(16 * 256)

for _b_idx in range(16):
    _d = BAYER4[_b_idx] - 7.5
    _d_rb = int(round(_d * 0.5))
    _d_g  = int(round(_d * 0.25))
    for _v in range(256):
        _vr = max(0, min(255, _v + _d_rb)) & 0xF8
        _vg = max(0, min(255, _v + _d_g))  & 0xFC
        _vb = max(0, min(255, _v + _d_rb)) >> 3
        _DITHER_TABLE_R[_b_idx * 256 + _v] = _vr
        _DITHER_TABLE_G[_b_idx * 256 + _v] = _vg
        _DITHER_TABLE_B[_b_idx * 256 + _v] = _vb


def pixel_to_rgb565_le(r: int, g: int, b: int) -> bytes:
    """
    Converts 8-bit RGB values to 16-bit RGB565 in Little-Endian byte order.
    Format:
      R: 5 bits (bits 15..11)
      G: 6 bits (bits 10..5)
      B: 5 bits (bits 4..0)
    """
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack("<H", val)


def convert_to_rgb565(
    source,
    target_width: Optional[int] = None,
    target_height: Optional[int] = None,
    dither: bool = True
) -> bytes:
    """
    Converts an image file path, PIL Image, or raw RGB buffer into an RGB565 Little-Endian buffer.
    Applies Bayer ordered dithering by default to eliminate color banding on gradients.
    """
    try:
        from PIL import Image
    except ImportError:
        Image = None

    if Image and isinstance(source, Image.Image):
        tw = target_width if target_width is not None else source.width
        th = target_height if target_height is not None else source.height
        if source.size != (tw, th):
            img = source.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
        else:
            img = source.convert("RGB")
        raw_rgb = img.tobytes()
    elif Image and isinstance(source, str):
        with Image.open(source) as img:
            tw = target_width if target_width is not None else 800
            th = target_height if target_height is not None else 480
            img = img.convert("RGB").resize((tw, th), Image.Resampling.LANCZOS)
            raw_rgb = img.tobytes()
    elif isinstance(source, (bytes, bytearray)):
        tw = target_width or 800
        th = target_height or 480
        expected_size = tw * th * 3
        if len(source) == expected_size:
            raw_rgb = bytes(source)
        elif len(source) == tw * th * 2:
            return bytes(source)
        else:
            raise ValueError(f"Raw buffer length {len(source)} does not match RGB888 ({expected_size}) or RGB565")
    else:
        raise TypeError("Source must be a file path, PIL Image, or RGB byte buffer")

    # High-performance conversion to RGB565 Little-Endian
    out = bytearray(tw * th * 2)
    in_idx = 0
    out_idx = 0

    if dither:
        for y in range(th):
            b_row = (y & 3) << 2
            for x in range(tw):
                b_base = (b_row | (x & 3)) << 8
                r = _DITHER_TABLE_R[b_base + raw_rgb[in_idx]]
                g = _DITHER_TABLE_G[b_base + raw_rgb[in_idx + 1]]
                b = _DITHER_TABLE_B[b_base + raw_rgb[in_idx + 2]]
                val = (r << 8) | (g << 3) | b
                out[out_idx] = val & 0xFF
                out[out_idx + 1] = (val >> 8) & 0xFF
                in_idx += 3
                out_idx += 2
    else:
        total_pixels = tw * th
        for _ in range(total_pixels):
            r = raw_rgb[in_idx]
            g = raw_rgb[in_idx + 1]
            b = raw_rgb[in_idx + 2]
            val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            out[out_idx] = val & 0xFF
            out[out_idx + 1] = (val >> 8) & 0xFF
            in_idx += 3
            out_idx += 2

    return bytes(out)

def create_test_pattern(width: int = 800, height: int = 480) -> bytes:
    """
    Generates a synthetic procedural test pattern (color gradient) without external dependencies.
    """
    buffer = bytearray(width * height * 2)
    idx = 0
    for y in range(height):
        # Y gradient from 0 to 255
        g = int((y / height) * 255)
        for x in range(width):
            # X gradient from 0 to 255
            r = int((x / width) * 255)
            # Diagonal blue
            b = int(((x + y) / (width + height)) * 255)
            val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buffer[idx] = val & 0xFF
            buffer[idx + 1] = (val >> 8) & 0xFF
            idx += 2
    return bytes(buffer)
