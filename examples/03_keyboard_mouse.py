"""Example: Keyboard and mouse input simulation with xdrive."""

from xdrive import XDrive, expect


def main():
    print("Starting virtual display for input simulation...")

    with XDrive(virtual=True, screen_size=(1280, 800)) as xd:
        win = xd.new_window(title="Input Demo", size=(600, 400), position=(100, 100))
        win.focus()
        xd.wait_for_layout()

        print(f"Created window: {win!r}")
        print(f"  Focused: {win.is_focused}")

        # ------------------------------------------------------------------
        # Mouse: move to window centre then click
        # ------------------------------------------------------------------
        geo = win.geometry
        cx = geo.x + geo.width // 2
        cy = geo.y + geo.height // 2

        print(f"\nMoving mouse to window centre ({cx}, {cy})")
        xd.mouse.move(cx, cy)

        print("Left-clicking window centre")
        xd.mouse.click()  # click at current position

        # ------------------------------------------------------------------
        # Mouse: move relative to origin
        # ------------------------------------------------------------------
        print("Moving mouse to (200, 200)")
        xd.mouse.move(200, 200)

        # ------------------------------------------------------------------
        # Keyboard: type a string
        # ------------------------------------------------------------------
        print("\nTyping 'hello world' into the focused window")
        xd.keyboard.type("hello world")

        # ------------------------------------------------------------------
        # Keyboard: press special keys
        # ------------------------------------------------------------------
        print("Pressing Return")
        xd.keyboard.press("Return")

        print("Pressing Ctrl+A (select all)")
        xd.keyboard.press("ctrl+a")

        print("Pressing Escape")
        xd.keyboard.press("Escape")

        # ------------------------------------------------------------------
        # Verify the window is still alive and mapped
        # ------------------------------------------------------------------
        expect(win).to_be_mapped()
        print("\nWindow still mapped after input — assertions passed.")

    print("Done.")


if __name__ == "__main__":
    main()
