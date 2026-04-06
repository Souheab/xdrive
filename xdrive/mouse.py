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
    """Mouse input controller using XTEST extension."""

    def __init__(self, display: Display):
        self._display = display

    def move(self, x: int, y: int) -> None:
        """Move the mouse cursor to absolute coordinates."""
        root = self._display.screen().root
        root.warp_pointer(x, y)
        self._display.flush()
        time.sleep(0.01)

    def move_to(self, target) -> None:
        """Move the mouse to the center of a window.

        ``target`` can be a Window or a _CloseButtonProxy.
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
        """Click a mouse button. If target is given, move there first."""
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
        self.click(target, button)
        time.sleep(0.05)
        self.click(target if target is None else None, button)

    def right_click(self, target=None) -> None:
        self.click(target, button=3)

    def scroll(self, target=None, direction: str = "up", amount: int = 1) -> None:
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
        btn = _BUTTON_MAP.get(button, button)
        xtest.fake_input(self._display, X.ButtonPress, btn)
        self._display.flush()

    def up(self, button: int = 1) -> None:
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

        Can be called as:
            drag(start_x, start_y, end_x, end_y)
            drag(window.frame, to_x=200, to_y=200)
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
        """Return the current mouse cursor position."""
        root = self._display.screen().root
        pointer = root.query_pointer()
        return (pointer.root_x, pointer.root_y)
