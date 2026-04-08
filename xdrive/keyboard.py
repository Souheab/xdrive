"""Keyboard input via XTEST extension."""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING

from Xlib import X, XK
from Xlib.ext import xtest

if TYPE_CHECKING:
    from Xlib.display import Display

# Map common key names to X11 keysym names
_KEY_ALIASES = {
    "Return": "Return",
    "Enter": "Return",
    "Tab": "Tab",
    "Escape": "Escape",
    "BackSpace": "BackSpace",
    "Delete": "Delete",
    "Home": "Home",
    "End": "End",
    "Page_Up": "Page_Up",
    "Page_Down": "Page_Down",
    "Left": "Left",
    "Right": "Right",
    "Up": "Up",
    "Down": "Down",
    "space": "space",
    "Space": "space",
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "F10": "F10",
    "F11": "F11",
    "F12": "F12",
}

_MODIFIER_MAP = {
    "shift": "Shift_L",
    "ctrl": "Control_L",
    "control": "Control_L",
    "alt": "Alt_L",
    "super": "Super_L",
    "meta": "Meta_L",
}


class Keyboard:
    """Synthesise keyboard input via the XTest X11 extension.

    Wraps ``Xlib.ext.xtest.fake_input`` to inject ``KeyPress`` and
    ``KeyRelease`` events into the X server.  Events are delivered to
    whichever window currently holds input focus on the connected
    DISPLAY.

    Args:
        display: An open ``Xlib.display.Display`` connection.

    Example:
        >>> kb = Keyboard(display)
        >>> kb.type("hello")
        >>> kb.press("ctrl+s")
    """

    def __init__(self, display: Display):
        self._display = display
        self._held_keys: list[int] = []

    def _resolve_keysym(self, key_name: str) -> int:
        """Resolve a human-readable key name to an X11 keysym.

        Handles modifier aliases (``ctrl``, ``alt``, …), common key names
        (``Return``, ``Escape``, …), and single characters.

        Args:
            key_name: Key identifier such as ``'a'``, ``'Return'``, or
                ``'ctrl'``.

        Returns:
            The integer X11 keysym.

        Raises:
            ValueError: If the key name cannot be resolved.
        """
        # Check modifier map
        lower = key_name.lower()
        if lower in _MODIFIER_MAP:
            xk_name = _MODIFIER_MAP[lower]
        elif key_name in _KEY_ALIASES:
            xk_name = _KEY_ALIASES[key_name]
        else:
            xk_name = key_name

        # Try XK lookup
        keysym = XK.string_to_keysym(xk_name)
        if keysym == 0:
            # Try as-is (single character)
            keysym = XK.string_to_keysym(key_name)
        if keysym == 0 and len(key_name) == 1:
            keysym = ord(key_name)
        if keysym == 0:
            raise ValueError(f"Unknown key: {key_name!r}")
        return keysym

    def _keysym_to_keycode(self, keysym: int) -> int:
        """Convert an X11 keysym to the corresponding keycode.

        Args:
            keysym: The keysym integer to look up.

        Returns:
            The hardware keycode registered for *keysym*.

        Raises:
            ValueError: If no keycode mapping exists.
        """
        keycode = self._display.keysym_to_keycode(keysym)
        if keycode == 0:
            raise ValueError(f"No keycode found for keysym {keysym}")
        return keycode

    def _press_key(self, keycode: int) -> None:
        xtest.fake_input(self._display, X.KeyPress, keycode)
        self._display.flush()

    def _release_key(self, keycode: int) -> None:
        xtest.fake_input(self._display, X.KeyRelease, keycode)
        self._display.flush()

    def type(self, text: str) -> None:
        """Type a string character by character, injecting XTest key events.

        Automatically holds ``Shift_L`` for uppercase letters and common
        shifted symbols.

        Args:
            text: Plain-text string to type.  Supports ``\\n`` (Return)
                and ``\\t`` (Tab).

        Example:
            >>> kb.type("Hello, world!\\n")
        """
        for char in text:
            if char == " ":
                keysym = XK.string_to_keysym("space")
            elif char == "\n":
                keysym = XK.string_to_keysym("Return")
            elif char == "\t":
                keysym = XK.string_to_keysym("Tab")
            else:
                keysym = ord(char)

            keycode = self._display.keysym_to_keycode(keysym)
            if keycode == 0:
                continue

            # Check if shift is needed (uppercase or shifted symbols)
            needs_shift = char.isupper() or char in '~!@#$%^&*()_+{}|:"<>?'
            if needs_shift:
                shift_keysym = XK.string_to_keysym("Shift_L")
                shift_keycode = self._display.keysym_to_keycode(shift_keysym)
                self._press_key(shift_keycode)

            self._press_key(keycode)
            time.sleep(0.005)
            self._release_key(keycode)

            if needs_shift:
                self._release_key(shift_keycode)

            time.sleep(0.005)

    def press(self, keys: str) -> None:
        """Press (and release) a key or key combination.

        Modifier and regular keys are separated by ``+``.  Keys are pressed
        in order and released in reverse order, matching the physical
        behaviour of a chord.

        Args:
            keys: Key combination string, e.g. ``'ctrl+shift+q'`` or
                ``'Return'``.

        Example:
            >>> kb.press("alt+F4")
        """
        parts = keys.split("+")
        keycodes = []

        for part in parts:
            part = part.strip()
            keysym = self._resolve_keysym(part)
            keycode = self._keysym_to_keycode(keysym)
            keycodes.append(keycode)

        # Press all keys in order
        for kc in keycodes:
            self._press_key(kc)
            time.sleep(0.005)

        # Release in reverse order
        for kc in reversed(keycodes):
            self._release_key(kc)
            time.sleep(0.005)

    def down(self, key: str) -> None:
        """Press and hold a key without releasing it.

        The keycode is recorded so that :meth:`up` can release it later.

        Args:
            key: Key name (e.g. ``'shift'``, ``'a'``).
        """
        keysym = self._resolve_keysym(key)
        keycode = self._keysym_to_keycode(keysym)
        self._press_key(keycode)
        self._held_keys.append(keycode)

    def up(self, key: str) -> None:
        """Release a previously held key.

        Args:
            key: Key name that was passed to :meth:`down`.
        """
        keysym = self._resolve_keysym(key)
        keycode = self._keysym_to_keycode(keysym)
        self._release_key(keycode)
        if keycode in self._held_keys:
            self._held_keys.remove(keycode)

    @contextlib.contextmanager
    def held(self, key: str):
        """Context manager that holds a key for the duration of a block.

        The key is pressed on entry and released on exit, even if an
        exception occurs.

        Args:
            key: Key name to hold (e.g. ``'shift'``, ``'ctrl'``).

        Example:
            >>> with kb.held("ctrl"):
            ...     kb.press("c")
        """
        self.down(key)
        try:
            yield
        finally:
            self.up(key)
