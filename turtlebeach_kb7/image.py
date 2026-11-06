"""
Image conversion utilities for Turtle Beach KB7 (800x480 RGB565 Little-Endian).
"""

import struct

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

def convert_to_rgb565(source, target_width: int = 800, target_height: int = 480) -> bytes:
    """
    Converts an image file path, PIL Image, or raw RGB buffer into an 800x480 RGB565 buffer.
    """
    try:
        from PIL import Image
    except ImportError:
        Image = None

    if Image and isinstance(source, Image.Image):
        img = source.convert("RGB").resize((target_width, target_height))
        raw_rgb = img.tobytes()
    elif Image and isinstance(source, str):
        with Image.open(source) as img:
            img = img.convert("RGB").resize((target_width, target_height))
            raw_rgb = img.tobytes()
    elif isinstance(source, (bytes, bytearray)):
        expected_size = target_width * target_height * 3
        if len(source) == expected_size:
            raw_rgb = bytes(source)
        elif len(source) == target_width * target_height * 2:
            return bytes(source)
        else:
            raise ValueError(f"Raw buffer length {len(source)} does not match RGB888 ({expected_size}) or RGB565")
    else:
        raise TypeError("Source must be a file path, PIL Image, or RGB byte buffer")

    # Fast conversion to RGB565
    out = bytearray(target_width * target_height * 2)
    in_idx = 0
    out_idx = 0
    total_pixels = target_width * target_height
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
