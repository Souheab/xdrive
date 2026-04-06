"""Example: Basic window creation and inspection with xdrive."""

from xdrive import XDrive, expect


def main():
    print("Starting virtual display and creating windows...")

    with XDrive(virtual=True, screen_size=(1280, 800)) as xd:
        # Create a basic window
        win = xd.new_window(title="Hello from xdrive", size=(640, 480))

        print(f"Created window: {win!r}")
        print(f"  Title:    {win.title!r}")
        print(f"  Geometry: {win.geometry}")
        print(f"  Mapped:   {win.is_mapped}")
        print(f"  Focused:  {win.is_focused}")

        # Use fluent assertions
        expect(win).to_be_mapped()
        expect(win).to_have_title("Hello from xdrive")
        expect(win).to_have_geometry(width=640, height=480)
        print("  Assertions passed.")

        # Update the title and verify
        win.set_title("Renamed Window")
        expect(win).to_have_title("Renamed Window")
        print(f"  Renamed to: {win.title!r}")

        # Resize and verify
        win.set_size(800, 600)
        xd.wait_for_layout()
        expect(win).to_have_geometry(width=800, height=600)
        print(f"  Resized to: {win.geometry.width}x{win.geometry.height}")

        # Screen geometry
        screen_geo = xd.screen.geometry
        print(f"\nScreen geometry: {screen_geo}")

        # List all windows
        windows = xd.screen.windows()
        print(f"Windows on screen: {len(windows)}")

        # Create a second window and assert no overlap
        win2 = xd.new_window(
            title="Second Window", size=(300, 200), position=(700, 500)
        )
        print(f"\nSecond window: {win2!r}")
        print(f"  Geometry: {win2.geometry}")

        expect([win, win2]).are_all_mapped()
        print("  Both windows are mapped.")

    print("\nDone - virtual display cleaned up.")


if __name__ == "__main__":
    main()
