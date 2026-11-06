"""
Turtle Beach Command Series KB7 - Display & Touch Protocol Library
Reverse engineered USB HID protocol for controlling the 4.3" touch display.
"""

from .device import KB7Device
from .image import convert_to_rgb565, create_test_pattern

__version__ = "1.0.0"
__all__ = ["KB7Device", "convert_to_rgb565", "create_test_pattern"]
