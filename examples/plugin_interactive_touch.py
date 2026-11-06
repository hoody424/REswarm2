"""
Example KB7 Plugin: Interactive Touch and Gesture Handler.

Demonstrates how custom plugins can connect to the running KB7 Daemon
using the KB7Client SDK, query device status, and react to touch events.
"""

import sys
import os
import time

# Add parent directory to module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from turtlebeach_kb7.client import KB7Client
from turtlebeach_kb7.widgets import (
    APP_CPU_USAGE,
    APP_GPU_USAGE,
    APP_SPEAKER_MUTE,
    APP_PLAY_PAUSE
)


def main():
    print("==================================================")
    print(" Turtle Beach KB7 Custom Plugin - Touch Handler")
    print("==================================================")

    client = KB7Client()
    try:
        client.connect()
        print("[+] Connected to KB7 Daemon successfully!")
    except ConnectionRefusedError:
        print("[!] Error: Could not connect to KB7 Daemon on 127.0.0.1:27878.")
        print("[!] Please start the daemon first with: python -m turtlebeach_kb7.cli daemon")
        return 1

    # Query current hardware settings via Daemon
    settings = client.get_settings()
    print(f"Current Settings: Brightness={settings['brightness']}%, Active Page={settings['active_page']}")

    # Configure a custom widget layout on Page 1
    print("\n[*] Assigning custom widgets to Page 1:")
    print("    Slot 0 -> CPU Load (AppID 1006)")
    print("    Slot 1 -> GPU Load (AppID 1007)")
    print("    Slot 2 -> Speaker Mute (AppID 25)")
    print("    Slot 3 -> Play/Pause (AppID 56)")
    client.assign_widget(page=1, slot=0, app_id=APP_CPU_USAGE)
    client.assign_widget(page=1, slot=1, app_id=APP_GPU_USAGE)
    client.assign_widget(page=1, slot=2, app_id=APP_SPEAKER_MUTE)
    client.assign_widget(page=1, slot=3, app_id=APP_PLAY_PAUSE)

    # Register event listeners
    @client.on_touch(slot=0, gesture="tap")
    def on_cpu_widget_tapped(event):
        print(f"\n[EVENT] CPU Widget (Slot 0) tapped! Position: ({event['x']}, {event['y']})")

    @client.on_touch(slot=1, gesture="tap")
    def on_gpu_widget_tapped(event):
        print(f"\n[EVENT] GPU Widget (Slot 1) tapped! Position: ({event['x']}, {event['y']})")

    @client.on_touch(slot=2, gesture="tap")
    def on_mute_tapped(event):
        print(f"\n[EVENT] Mute Widget (Slot 2) tapped! Toggling mute...")

    @client.on_touch(gesture="swipe_left")
    def on_swipe_left(event):
        print("\n[EVENT] Swipe Left detected! Switching to next page...")

    @client.on_touch(gesture="swipe_right")
    def on_swipe_right(event):
        print("\n[EVENT] Swipe Right detected! Switching to previous page...")

    # Catch-all logger for any touch
    @client.on_touch()
    def on_any_touch(event):
        print(f"Touch: Gesture={event['gesture']:<11} | Slot={event['slot_id']:2d} | Coord=({event['x']:3d}, {event['y']:3d})")

    print("\n[*] Plugin listening for touch events from KB7 Display (Ctrl+C to stop)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping plugin.")
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
