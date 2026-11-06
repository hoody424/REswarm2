"""
Turtle Beach Command Series KB7 - Display & Touch Protocol Library
Reverse engineered USB HID protocol for controlling the 4.3" touch display.
"""

from .device import KB7Device
from .image import convert_to_rgb565, create_test_pattern
from .client import KB7Client
from .daemon import KB7Daemon
from .audio_mixer import UniversalAudioMixer, AudioSessionItem, AudioDeviceItem, AppGroup

__version__ = "1.1.0"
__all__ = [
    "KB7Device",
    "KB7Client",
    "KB7Daemon",
    "UniversalAudioMixer",
    "AudioSessionItem",
    "AudioDeviceItem",
    "AppGroup",
    "convert_to_rgb565",
    "create_test_pattern",
]
