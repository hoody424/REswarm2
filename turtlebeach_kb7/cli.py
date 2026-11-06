"""
Command-Line Interface (CLI) for Turtle Beach Command Series KB7.
"""

import sys
import time
import argparse
from .device import KB7Device, SLOT_BACKGROUND
from .image import convert_to_rgb565, create_test_pattern
from .win_hid import enumerate_kb7_endpoints

def cmd_info(args):
    print("==================================================")
    print(" Turtle Beach Command Series KB7 Hardware Overview")
    print("==================================================")
    endpoints = enumerate_kb7_endpoints()
    if not endpoints:
        print("[!] No Turtle Beach KB7 (VID 0x10F5, PID 0x5038) found.")
        return 1

    print(f"Found {len(endpoints)} HID interface collections:\n")
    for idx, ep in enumerate(endpoints):
        desc = "Unknown"
        up, u = ep["usage_page"], ep["usage"]
        if up == 0xFF90:
            desc = "Sonix Bootloader ISP & Core Config"
        elif up == 0xFF00 and u == 0x0001:
            desc = "LCD DISPLAY CONTROLLER & STREAMING (mi_01)"
        elif up == 0x000C:
            desc = "Consumer Media Keys"
        elif up == 0x0001 and u == 0x0080:
            desc = "System Control (Power/Sleep)"
        elif up == 0xFF01:
            desc = "Hardware Event Stream 1"
        elif up == 0xFF02:
            desc = "TOUCHSCREEN INPUT DIGITIZER (mi_02 COL04)"
        elif up == 0x0001 and u == 0x0006:
            desc = "Keyboard Scan Codes (8000 Hz Polling)"
        elif up == 0xFF03:
            desc = "Lighting Animations & Profiles (Feature Report)"

        print(f"[{idx+1}] UsagePage: 0x{up:04X}, Usage: 0x{u:04X}")
        print(f"    Role: {desc}")
        print(f"    InputLen: {ep['input_len']}B, OutputLen: {ep['output_len']}B, FeatureLen: {ep['feature_len']}B")
        print(f"    Path: {ep['path']}\n")

    return 0

def cmd_upload(args):
    print(f"Connecting to Turtle Beach KB7 Display...")
    device = KB7Device()
    device.connect()

    if args.test_pattern:
        print("Generating 800x480 test gradient pattern...")
        rgb565 = create_test_pattern(800, 480)
    elif args.file:
        print(f"Converting '{args.file}' to 800x480 RGB565 Little-Endian...")
        rgb565 = convert_to_rgb565(args.file, 800, 480)
    else:
        print("[!] Error: Either specify an image file or pass --test-pattern")
        return 1

    start_time = time.time()

    def progress(sent, total):
        pct = (sent / total) * 100
        bar = "#" * int(pct // 5) + "-" * (20 - int(pct // 5))
        sys.stdout.write(f"\rUploading: [{bar}] {pct:5.1f}% ({sent}/{total} bytes)")
        sys.stdout.flush()

    print("Streaming image data over USB HID (mi_01)...")
    try:
        device.upload_image(rgb565, slot_id=SLOT_BACKGROUND, progress_callback=progress)
        duration = time.time() - start_time
        print(f"\n[+] Success! Image uploaded in {duration:.2f}s ({len(rgb565) / duration / 1024:.1f} KB/s)")
    finally:
        device.disconnect()

    return 0

def cmd_touch(args):
    print("Connecting to Turtle Beach KB7 Touch Digitizer...")
    device = KB7Device()
    device.connect()

    if not device.touch_handle:
        print("[!] Error: Touch interface (0xFF02:0x0001) could not be opened.")
        return 1

    print("[*] Listening for touch events on 4.3\" display (Ctrl+C to stop)...")
    try:
        while True:
            event = device.read_touch_event(timeout_ms=500)
            if event:
                print(f"Touch Event: Type=0x{event['event_type']:02X} | Gesture={event['gesture']:<4} | Slot={event['slot_id']:2d} | Coord=({event['x']:3d}, {event['y']:3d}) | Raw={event['raw']}")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        device.disconnect()

    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Turtle Beach Command Series KB7 Touch Display & HID Reverse Engineering Tool"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Info
    p_info = subparsers.add_parser("info", help="Show connected endpoints and status")
    p_info.set_defaults(func=cmd_info)

    # Upload
    p_upload = subparsers.add_parser("upload", help="Upload wallpaper or widget to display")
    p_upload.add_argument("file", nargs="?", help="Path to image file (PNG, JPG, BMP)")
    p_upload.add_argument("--test-pattern", action="store_true", help="Send procedural color test pattern")
    p_upload.set_defaults(func=cmd_upload)

    # Touch
    p_touch = subparsers.add_parser("touch", help="Listen for touch screen coordinates and gestures")
    p_touch.set_defaults(func=cmd_touch)

    args = parser.parse_args()
    sys.exit(args.func(args))

if __name__ == "__main__":
    main()
