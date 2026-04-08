"""Mouse input via XTEST extension."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from Xlib import X
from Xlib.ext import xtest

if TYPE_CHECKING:
    from Xlib.display import Display

    from .window import Window


# X11 button mappings
_BUTTON_MAP = {
    1: 1,  # left
    2: 2,  # middle
    3: 3,  # right
}

_SCROLL_MAP = {
    "up": 4,
    "down": 5,
    "left": 6,
    "right": 7,
}


class Mouse:
    """Synthesise mouse input via the XTest X11 extension.

    Uses ``Xlib.ext.xtest.fake_input`` to inject ``ButtonPress``,
    ``ButtonRelease``, and pointer-warp events.  Coordinates are
    always root-window-absolute.

    Args:
        display: An open ``Xlib.display.Display`` connection.

    Example:
        >>> mouse = Mouse(display)
        >>> mouse.move(100, 200)
        >>> mouse.click()
    """

    def __init__(self, display: Display):
        self._display = display

    def move(self, x: int, y: int) -> None:
        """Warp the pointer to absolute root-window coordinates.

        Args:
            x: Horizontal position in pixels from the left edge.
            y: Vertical position in pixels from the top edge.
        """
        root = self._display.screen().root
        root.warp_pointer(x, y)
        self._display.flush()
        time.sleep(0.01)

    def move_to(self, target) -> None:
        """Move the pointer to the centre of a window or close-button proxy.

        Args:
            target: A :class:`~xdrive.window.Window` or
                ``_CloseButtonProxy`` instance.

        Raises:
            TypeError: If *target* is not a supported type.
        """
        from .window import Window, _CloseButtonProxy

        if isinstance(target, _CloseButtonProxy):
            x, y = target.position
            self.move(x, y)
        elif isinstance(target, Window):
            geo = target.geometry
            cx = geo.x + geo.width // 2
            cy = geo.y + geo.height // 2
            self.move(cx, cy)
        else:
            raise TypeError(f"Cannot move to {type(target)}")

    def click(self, target=None, button: int = 1) -> None:
        """Click a mouse button, optionally on a specific target.

        Injects a ``ButtonPress`` followed by a ``ButtonRelease`` via
        XTest.

        Args:
            target: Optional :class:`~xdrive.window.Window` or
                ``_CloseButtonProxy`` to move to before clicking.
            button: X11 button number (1 = left, 2 = middle,
                3 = right).

        Example:
            >>> mouse.click(win)          # left-click on window
            >>> mouse.click(button=3)     # right-click at current pos
        """
        if target is not None:
            self.move_to(target)
        btn = _BUTTON_MAP.get(button, button)
        xtest.fake_input(self._display, X.ButtonPress, btn)
        self._display.flush()
        time.sleep(0.01)
        xtest.fake_input(self._display, X.ButtonRelease, btn)
        self._display.flush()
        time.sleep(0.01)

    def double_click(self, target=None, button: int = 1) -> None:
        """Perform a double-click.

        Args:
            target: Optional window or proxy to move to first.
            button: X11 button number.
        """
        self.click(target, button)
        time.sleep(0.05)
        self.click(target if target is None else None, button)

    def right_click(self, target=None) -> None:
        """Convenience wrapper for a button-3 (right) click.

        Args:
            target: Optional window or proxy to move to first.
        """
        self.click(target, button=3)

    def scroll(self, target=None, direction: str = "up", amount: int = 1) -> None:
        """Scroll the mouse wheel.

        X11 maps scroll directions to button numbers 4–7.

        Args:
            target: Optional window or proxy to move to first.
            direction: One of ``'up'``, ``'down'``, ``'left'``,
                ``'right'``.
            amount: Number of scroll "clicks" to inject.

        Raises:
            ValueError: If *direction* is unrecognised.
        """
        if target is not None:
            self.move_to(target)
        btn = _SCROLL_MAP.get(direction)
        if btn is None:
            raise ValueError(f"Unknown scroll direction: {direction}")
        for _ in range(amount):
            xtest.fake_input(self._display, X.ButtonPress, btn)
            self._display.flush()
            xtest.fake_input(self._display, X.ButtonRelease, btn)
            self._display.flush()
            time.sleep(0.01)

    def down(self, button: int = 1) -> None:
        """Press and hold a mouse button.

        Args:
            button: X11 button number.
        """
        btn = _BUTTON_MAP.get(button, button)
        xtest.fake_input(self._display, X.ButtonPress, btn)
        self._display.flush()

    def up(self, button: int = 1) -> None:
        """Release a held mouse button.

        Args:
            button: X11 button number.
        """
        btn = _BUTTON_MAP.get(button, button)
        xtest.fake_input(self._display, X.ButtonRelease, btn)
        self._display.flush()

    def drag(
        self,
        start_or_window=None,
        start_y: int | None = None,
        end_x: int | None = None,
        end_y: int | None = None,
        *,
        to_x: int | None = None,
        to_y: int | None = None,
        button: int = 1,
    ) -> None:
        """Drag from one position to another.

        Supports two calling conventions:

        * ``drag(start_x, start_y, end_x, end_y)`` — absolute coords.
        * ``drag(window, to_x=x, to_y=y)`` — from window centre to
          absolute coords.

        Args:
            start_or_window: Starting X coordinate **or** a
                :class:`~xdrive.window.Window` to start from.
            start_y: Starting Y coordinate (positional form).
            end_x: Ending X coordinate (positional form).
            end_y: Ending Y coordinate (positional form).
            to_x: Destination X (keyword form).
            to_y: Destination Y (keyword form).
            button: X11 button number to hold during the drag.

        Raises:
            ValueError: If the arguments don't match either form.

        Example:
            >>> mouse.drag(win.frame, to_x=200, to_y=200)
        """
        from .window import Window

        if isinstance(start_or_window, Window):
            # drag(window, to_x=..., to_y=...)
            self.move_to(start_or_window)
            time.sleep(0.02)
            self.down(button)
            time.sleep(0.02)
            if to_x is not None and to_y is not None:
                self.move(to_x, to_y)
            time.sleep(0.02)
            self.up(button)
        else:
            # drag(start_x, start_y, end_x, end_y)
            sx = start_or_window
            sy = start_y
            ex = end_x
            ey = end_y
            if sx is None or sy is None or ex is None or ey is None:
                raise ValueError(
                    "drag requires either (window, to_x, to_y) or (start_x, start_y, end_x, end_y)"
                )
            self.move(sx, sy)
            time.sleep(0.02)
            self.down(button)
            time.sleep(0.02)
            self.move(ex, ey)
            time.sleep(0.02)
            self.up(button)

        self._display.flush()

    def position(self) -> tuple[int, int]:
        """Return the current pointer position in root-window coordinates.

        Returns:
            A ``(x, y)`` tuple.
        """
        root = self._display.screen().root
        pointer = root.query_pointer()
        return (pointer.root_x, pointer.root_y)
