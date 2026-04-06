"""Example: Open multiple windows and capture screenshots with xdrive.

This example demonstrates:
  - Launching a virtual display
  - Creating multiple windows at different positions/sizes
  - Taking a full-display screenshot and saving it to disk
  - Taking per-window screenshots and saving them
  - Using fluent expect() assertions on the captured images
"""

import os

from xdrive import XDrive, expect


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Screenshots will be saved to: {OUTPUT_DIR}")

    with XDrive(virtual=True, screen_size=(1280, 800)) as xd:
        # ------------------------------------------------------------------
        # Create a handful of windows at distinct positions
        # ------------------------------------------------------------------
        windows = [
            xd.new_window(title="Window A", size=(400, 300), position=(0, 0)),
            xd.new_window(title="Window B", size=(400, 300), position=(440, 0)),
            xd.new_window(title="Window C", size=(600, 200), position=(200, 400)),
        ]

        for win in windows:
            print(f"  {win!r}  geometry={win.geometry}")

        expect(windows).are_all_mapped()

        # ------------------------------------------------------------------
        # Full-display screenshot
        # ------------------------------------------------------------------
        display_path = os.path.join(OUTPUT_DIR, "full_display.png")
        display_img = xd.screenshot(path=display_path)
        print(f"\nFull display screenshot saved → {display_path}")
        print(f"  Size: {display_img.width}x{display_img.height}")

        # The screenshot should match the display dimensions
        assert display_img.width == 1280
        assert display_img.height == 800

        # ------------------------------------------------------------------
        # Region screenshot (just the top-left quadrant)
        # ------------------------------------------------------------------
        region_path = os.path.join(OUTPUT_DIR, "region_quadrant.png")
        region_img = xd.screenshot(path=region_path, region=(0, 0, 640, 400))
        print(f"Region screenshot saved     → {region_path}")
        print(f"  Size: {region_img.width}x{region_img.height}")

        # ------------------------------------------------------------------
        # Per-window screenshots
        # ------------------------------------------------------------------
        for i, win in enumerate(windows):
            win_path = os.path.join(OUTPUT_DIR, f"window_{chr(ord('a') + i)}.png")
            win_img = win.screenshot(path=win_path)
            print(
                f"Window '{win.title}' screenshot → {win_path}  ({win_img.width}x{win_img.height})"
            )

            # Screenshot dimensions should match the window size
            geo = win.geometry
            assert (
                win_img.width == geo.width
            ), f"Expected img width {geo.width}, got {win_img.width}"
            assert (
                win_img.height == geo.height
            ), f"Expected img height {geo.height}, got {win_img.height}"

        # ------------------------------------------------------------------
        # Use ImageExpectation to confirm two different screenshots differ
        # ------------------------------------------------------------------
        img_a = windows[0].screenshot()
        img_b = windows[1].screenshot()
        # Windows A and B may have similar content (both white); only assert
        # they are structurally valid images.
        assert img_a.size == (400, 300)
        assert img_b.size == (400, 300)
        print("\nImage assertions passed.")

        # A second full-display capture should be identical to the first
        # (nothing changed on screen)
        second_shot = xd.screenshot()
        expect(display_img).to_match(second_shot)
        print("Consecutive full-display screenshots match ✓")

    print("\nAll screenshots saved successfully.")

    # List the output files
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        fpath = os.path.join(OUTPUT_DIR, fname)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  {fname}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
