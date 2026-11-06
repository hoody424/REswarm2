"""
Example: Real-time touch event listener for Turtle Beach KB7.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from turtlebeach_kb7.device import KB7Device

def main():
    print("=== Turtle Beach KB7 Touch Event Monitor ===")
    print("Touch anywhere on the 4.3\" keyboard screen. Press Ctrl+C to exit.\n")

    with KB7Device() as kb7:
        if not kb7.touch_handle:
            print("[!] Could not open touch interface (UsagePage 0xFF02, Usage 0x0001).")
            return

        print(f"Monitoring: {kb7.touch_path}\n")
        try:
            while True:
                ev = kb7.read_touch_event(timeout_ms=500)
                if ev:
                    print(
                        f"Gesture: {ev['gesture']:<4} | Slot: {ev['slot_id']:2d} | "
                        f"Coordinates: X={ev['x']:3d}, Y={ev['y']:3d} | Raw: {ev['raw']}"
                    )
        except KeyboardInterrupt:
            print("\nExiting listener.")

if __name__ == "__main__":
    main()
