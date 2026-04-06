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
    """Keyboard input controller using XTEST extension."""

    def __init__(self, display: Display):
        self._display = display
        self._held_keys: list[int] = []

    def _resolve_keysym(self, key_name: str) -> int:
        """Resolve a key name to an X11 keysym."""
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
        """Convert a keysym to a keycode."""
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
        """Type a string of text, character by character."""
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
        """Press a key or key combination (e.g. 'ctrl+shift+q', 'Return')."""
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
        """Press and hold a key."""
        keysym = self._resolve_keysym(key)
        keycode = self._keysym_to_keycode(keysym)
        self._press_key(keycode)
        self._held_keys.append(keycode)

    def up(self, key: str) -> None:
        """Release a held key."""
        keysym = self._resolve_keysym(key)
        keycode = self._keysym_to_keycode(keysym)
        self._release_key(keycode)
        if keycode in self._held_keys:
            self._held_keys.remove(keycode)

    @contextlib.contextmanager
    def held(self, key: str):
        """Context manager to hold a key while executing a block."""
        self.down(key)
        try:
            yield
        finally:
            self.up(key)
