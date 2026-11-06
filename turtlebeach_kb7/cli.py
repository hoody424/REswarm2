"""
Command-Line Interface (CLI) for Turtle Beach Command Series KB7.
"""

import sys
import os
import time
import argparse

try:
    from .device import KB7Device, SLOT_BACKGROUND
    from .image import convert_to_rgb565, create_test_pattern
    from .win_hid import enumerate_kb7_endpoints
    from .widgets import WIDGET_CATALOG, LAYOUT_TEMPLATES, lookup_widget
except ImportError:
    # Allow running directly as a standalone script
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from turtlebeach_kb7.device import KB7Device, SLOT_BACKGROUND
    from turtlebeach_kb7.image import convert_to_rgb565, create_test_pattern
    from turtlebeach_kb7.win_hid import enumerate_kb7_endpoints
    from turtlebeach_kb7.widgets import WIDGET_CATALOG, LAYOUT_TEMPLATES, lookup_widget


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
            desc = "LCD SETTINGS, PROFILES & LIGHTING (Feature Report mi_02 COL06)"

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


def cmd_brightness(args):
    with KB7Device() as dev:
        if args.value is not None:
            val = int(args.value)
            print(f"[*] Setting screen brightness to {val}%...")
            dev.set_brightness(val)
        settings = dev.get_lcd_settings()
        print(f"[+] Screen Brightness: {settings.brightness}%")
    return 0


def cmd_timeout(args):
    with KB7Device() as dev:
        if args.seconds is not None:
            sec = int(args.seconds)
            print(f"[*] Setting screen timeout to {sec}s...")
            dev.set_timeout(sec)
        settings = dev.get_lcd_settings()
        print(f"[+] Screen Sleep Timeout: {settings.timeout_seconds}s")
    return 0


def cmd_page(args):
    with KB7Device() as dev:
        if args.page_num is not None:
            p = int(args.page_num)
            print(f"[*] Switching active page to Page {p}...")
            dev.set_active_page(p)
        settings = dev.get_lcd_settings()
        print(f"[+] Active Display Page: Page {settings.active_page}")
    return 0


def cmd_keys(args):
    with KB7Device() as dev:
        keys = dev.get_screen_keys()
        print(f"==================================================")
        print(f" Virtual Touch Keys (Numpad / Macros) - {len(keys)} defined")
        print(f"==================================================")
        for k in keys:
            print(f"  Slot {k.index:02d} -> VirtualKey 0x{k.key_code:02X} | Mod: 0x{k.modifiers:02X} | Label: '{k.label}'")
    return 0


def cmd_slots(args):
    with KB7Device() as dev:
        settings = dev.get_lcd_settings()
        print("==================================================")
        print(f" Display Widget Slots (Active Page: {settings.active_page})")
        print("==================================================")
        slots = settings.widget_slots
        # 35 slots across 5 pages (7 slots/page configured in settings table)
        for i, (w_type, w_id) in enumerate(slots):
            page_num = (i // 7) + 1
            slot_on_page = i % 7
            if args.page and page_num != args.page:
                continue
            w_def = lookup_widget(w_id)
            status_desc = f"{w_def.name} ({w_def.category})" if w_id != 0 else "(Empty)"
            rt = "[Telemetry]" if w_def.runtime_update else ""
            print(f"  Page {page_num} Slot {slot_on_page} (Idx {i:02d}): Type={w_type:2d}, AppID={w_id:4d} -> {status_desc} {rt}")
    return 0


def cmd_templates(args):
    print("==================================================")
    print(" Predefined KB7 Layout Templates")
    print("==================================================")
    for name, slot_apps in LAYOUT_TEMPLATES.items():
        print(f"\nTemplate '{name}':")
        for idx, app_id in enumerate(slot_apps):
            w = lookup_widget(app_id)
            print(f"  Slot {idx:02d}: {w.name:<25} ({w.category})")
    return 0


def cmd_template(args):
    with KB7Device() as dev:
        name = args.name.lower()
        page = args.page
        print(f"[*] Applying template '{name}' to Page {page}...")
        dev.apply_template(page - 1, name)
        print(f"[+] Successfully applied template '{name}' to Page {page}!")
    return 0


def cmd_assign(args):
    with KB7Device() as dev:
        page = args.page
        slot = args.slot
        app_id = args.app_id
        w_def = lookup_widget(app_id)
        w_type = 2 if w_def.runtime_update else 3
        print(f"[*] Assigning Widget {w_def.name} (AppID {app_id}, Type {w_type}) to Page {page}, Slot {slot}...")
        dev.update_widget_slot(page - 1, slot, w_type, app_id, is_last=True)
        print(f"[+] Widget assigned successfully!")
    return 0


def cmd_daemon(args):
    from .daemon import run_daemon
    print("==================================================")
    print(" Turtle Beach Command Series KB7 Hardware Daemon")
    print("==================================================")
    run_daemon(host=args.host, port=args.port)
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

    # Brightness
    p_bri = subparsers.add_parser("brightness", help="Get or set screen brightness (0-100)")
    p_bri.add_argument("value", nargs="?", type=int, help="Brightness percentage (0-100)")
    p_bri.set_defaults(func=cmd_brightness)

    # Timeout
    p_to = subparsers.add_parser("timeout", help="Get or set screen sleep timeout in seconds")
    p_to.add_argument("seconds", nargs="?", type=int, help="Timeout in seconds")
    p_to.set_defaults(func=cmd_timeout)

    # Page
    p_page = subparsers.add_parser("page", help="Get or set active display page (1-5)")
    p_page.add_argument("page_num", nargs="?", type=int, help="Page number (1-5)")
    p_page.set_defaults(func=cmd_page)

    # Keys
    p_keys = subparsers.add_parser("keys", help="List virtual touch screen keys")
    p_keys.set_defaults(func=cmd_keys)

    # Slots
    p_slots = subparsers.add_parser("slots", help="List configured widget slots across pages")
    p_slots.add_argument("--page", type=int, help="Filter by page number (1-5)")
    p_slots.set_defaults(func=cmd_slots)

    # Templates
    p_tmpls = subparsers.add_parser("templates", help="List all available predefined layout templates")
    p_tmpls.set_defaults(func=cmd_templates)

    # Apply Template
    p_tmpl = subparsers.add_parser("template", help="Apply a predefined layout template to a display page")
    p_tmpl.add_argument("name", help="Template name (e.g. numpad, telemetry, productivity, multimedia, gaming, cs2, obs)")
    p_tmpl.add_argument("--page", type=int, default=1, help="Target page number (1-5, default: 1)")
    p_tmpl.set_defaults(func=cmd_template)

    # Assign Widget
    p_assign = subparsers.add_parser("assign", help="Assign a specific widget AppID to a page & slot")
    p_assign.add_argument("page", type=int, help="Page number (1-5)")
    p_assign.add_argument("slot", type=int, help="Slot index (0-12)")
    p_assign.add_argument("app_id", type=int, help="Widget AppID (e.g. 1006 for CPU, 1007 for GPU)")
    p_assign.set_defaults(func=cmd_assign)

    # Daemon
    p_daemon = subparsers.add_parser("daemon", help="Run background single-writer hardware daemon for plugins")
    p_daemon.add_argument("--host", default="127.0.0.1", help="Bind IP address (default: 127.0.0.1)")
    p_daemon.add_argument("--port", type=int, default=27878, help="TCP port (default: 27878)")
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
