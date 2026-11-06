"""
Example: Uploading a custom wallpaper or test pattern to the Turtle Beach KB7 Display.
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from turtlebeach_kb7.device import KB7Device, SLOT_BACKGROUND
from turtlebeach_kb7.image import create_test_pattern, convert_to_rgb565

def main():
    print("=== Turtle Beach KB7 Background Upload Example ===")

    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    if image_path:
        print(f"Loading '{image_path}'...")
        rgb565 = convert_to_rgb565(image_path, 800, 480)
    else:
        print("No image file specified; creating procedural 800x480 RGB gradient...")
        rgb565 = create_test_pattern(800, 480)

    print(f"Buffer size: {len(rgb565)} bytes ({len(rgb565)/1024:.1f} KB)")

    with KB7Device() as kb7:
        print(f"Connected to Display Interface: {kb7.display_path}")

        def on_progress(sent, total):
            pct = (sent / total) * 100
            sys.stdout.write(f"\rProgress: {pct:5.1f}% ({sent}/{total} bytes)")
            sys.stdout.flush()

        start = time.time()
        print("Uploading to Display...")
        kb7.upload_image(rgb565, slot_id=SLOT_BACKGROUND, progress_callback=on_progress)
        elapsed = time.time() - start
        print(f"\nDone! Elapsed time: {elapsed:.2f} seconds.")

if __name__ == "__main__":
    main()
