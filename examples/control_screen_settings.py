#!/usr/bin/env python3
"""
Example: Read and Control KB7 LCD Screen Settings (Brightness, Timeout, Screen Keys).
"""

import sys
import os

# Add parent directory to module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from turtlebeach_kb7.device import KB7Device


def main():
    print("=" * 65)
    print(" Turtle Beach Command Series KB7 - Display Settings Controller")
    print("=" * 65)

    with KB7Device() as dev:
        print("[+] Connected to KB7 hardware endpoints.")

        # 1. Query LCD Settings
        settings = dev.get_lcd_settings()
        print(f"\n[LCD Display Settings]")
        print(f"  * Active Page:           Page {settings.active_page}")
        print(f"  * Current Brightness:    {settings.brightness}%")
        print(f"  * Screen Sleep Timeout:  {settings.timeout_seconds} seconds")
        print(f"  * Screen Dim Timeout:    {settings.dim_timeout_seconds} seconds")
        print(f"  * Configured Slots:      {len(settings.widget_slots)} slots")

        # 2. Query Virtual Screen Keys
        keys = dev.get_screen_keys()
        print(f"\n[Virtual Screen Keys (Numpad / Macro Keys) - {len(keys)} defined]")
        for k in keys:
            print(f"  Slot {k.index:02d} -> VK 0x{k.key_code:02X} | Modifiers: 0x{k.modifiers:02X} | Label: '{k.label}'")

        # 3. Optional interactive or demonstration brightness test
        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            if cmd == "brightness" and len(sys.argv) > 2:
                new_bri = int(sys.argv[2])
                print(f"\n[*] Updating brightness to {new_bri}%...")
                dev.set_brightness(new_bri)
                updated = dev.get_lcd_settings()
                print(f"[+] Brightness updated: {updated.brightness}%")
            elif cmd == "timeout" and len(sys.argv) > 2:
                new_to = int(sys.argv[2])
                print(f"\n[*] Updating screen timeout to {new_to}s...")
                dev.set_timeout(new_to)
                updated = dev.get_lcd_settings()
                print(f"[+] Timeout updated: {updated.timeout_seconds}s")
            elif cmd == "page" and len(sys.argv) > 2:
                new_page = int(sys.argv[2])
                print(f"\n[*] Switching active page to Page {new_page}...")
                dev.set_active_page(new_page)
                updated = dev.get_lcd_settings()
                print(f"[+] Active page updated: Page {updated.active_page}")


if __name__ == "__main__":
    main()
