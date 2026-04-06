"""Window object representing an X11 window."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from PIL import Image
from Xlib import X, Xatom, Xutil

from .geometry import Geometry

if TYPE_CHECKING:
    from Xlib.display import Display
    from Xlib.xobject.drawable import Window as XWindow


class Window:
    """Represents a client or frame window in X11."""

    def __init__(self, xwindow: XWindow, display: Display, is_frame: bool = False):
        self._xwindow = xwindow
        self._display = display
        self._is_frame = is_frame
        self._frame_window: Window | None = None
        self._close_button: _CloseButtonProxy | None = None

    @property
    def id(self) -> int:
        return self._xwindow.id

    @property
    def title(self) -> str:
        """Get the window title (WM_NAME or _NET_WM_NAME)."""
        # Try _NET_WM_NAME first (UTF-8)
        net_wm_name = self._display.intern_atom("_NET_WM_NAME")
        utf8_string = self._display.intern_atom("UTF8_STRING")
        prop = self._xwindow.get_full_property(net_wm_name, utf8_string)
        if prop and prop.value:
            val = prop.value
            if isinstance(val, bytes):
                return val.decode("utf-8", errors="replace")
            return str(val)

        # Fall back to WM_NAME
        prop = self._xwindow.get_full_property(Xatom.WM_NAME, Xatom.STRING)
        if prop and prop.value:
            val = prop.value
            if isinstance(val, bytes):
                return val.decode("latin-1", errors="replace")
            return str(val)

        return ""

    @property
    def geometry(self) -> Geometry:
        geo = self._xwindow.get_geometry()
        # Translate coordinates to root window
        try:
            translated = self._xwindow.translate_coords(
                self._display.screen().root, 0, 0
            )
            return Geometry(
                x=-translated.x, y=-translated.y, width=geo.width, height=geo.height
            )
        except Exception:
            return Geometry(x=geo.x, y=geo.y, width=geo.width, height=geo.height)

    @property
    def frame(self) -> Window:
        """Get the WM frame window wrapping this client."""
        if self._is_frame:
            return self
        if self._frame_window is not None:
            return self._frame_window

        # Walk up the window tree to find the frame
        win = self._xwindow
        root = self._display.screen().root
        while True:
            parent = win.query_tree().parent
            if parent is None or parent.id == root.id:
                break
            win = parent

        if win.id != self._xwindow.id:
            self._frame_window = Window(win, self._display, is_frame=True)
            self._frame_window._close_button = _CloseButtonProxy(self._frame_window)
        else:
            self._frame_window = self
        return self._frame_window

    @property
    def close_button(self) -> "_CloseButtonProxy":
        """Proxy for the close button on the frame titlebar."""
        if self._close_button is None:
            self._close_button = _CloseButtonProxy(self)
        return self._close_button

    @property
    def is_mapped(self) -> bool:
        attrs = self._xwindow.get_attributes()
        return attrs.map_state != X.IsUnmapped

    @property
    def is_focused(self) -> bool:
        focused = self._display.get_input_focus().focus
        if hasattr(focused, "id"):
            # Check if the focused window is this window or its frame
            if focused.id == self._xwindow.id:
                return True
            # Check frame
            try:
                frame = self.frame
                if frame and focused.id == frame.id:
                    return True
            except Exception:
                pass
            # Check if focused window is a child of our frame
            try:
                frame = self.frame
                if frame:
                    children = frame._xwindow.query_tree().children
                    for child in children:
                        if child.id == focused.id:
                            return True
            except Exception:
                pass
        return False

    @property
    def is_fullscreen(self) -> bool:
        net_wm_state = self._display.intern_atom("_NET_WM_STATE")
        fullscreen_atom = self._display.intern_atom("_NET_WM_STATE_FULLSCREEN")
        prop = self._xwindow.get_full_property(net_wm_state, Xatom.ATOM)
        if prop and prop.value:
            atoms = prop.value
            if isinstance(atoms, bytes):
                atoms = struct.unpack(f"{len(atoms)//4}I", atoms)
            return fullscreen_atom in atoms
        return False

    def close(self) -> None:
        """Send WM_DELETE_WINDOW to gracefully close the window."""
        wm_protocols = self._display.intern_atom("WM_PROTOCOLS")
        wm_delete = self._display.intern_atom("WM_DELETE_WINDOW")

        event = Xlib_client_message(
            self._display, self._xwindow, wm_protocols, [wm_delete, X.CurrentTime]
        )
        self._xwindow.send_event(event)
        self._display.flush()

    def kill(self) -> None:
        """Forcefully destroy the window."""
        self._xwindow.destroy()
        self._display.flush()

    def focus(self) -> None:
        """Request input focus on this window."""
        self._xwindow.set_input_focus(X.RevertToParent, X.CurrentTime)
        self._xwindow.raise_window()
        self._display.flush()

    def set_title(self, title: str) -> None:
        net_wm_name = self._display.intern_atom("_NET_WM_NAME")
        utf8_string = self._display.intern_atom("UTF8_STRING")
        self._xwindow.change_property(
            net_wm_name, utf8_string, 8, title.encode("utf-8")
        )
        self._xwindow.change_property(
            Xatom.WM_NAME, Xatom.STRING, 8, title.encode("latin-1", errors="replace")
        )
        self._display.flush()

    def set_size(self, width: int, height: int) -> None:
        self._xwindow.configure(width=width, height=height)
        self._display.flush()

    def set_fullscreen(self, enabled: bool = True) -> None:
        net_wm_state = self._display.intern_atom("_NET_WM_STATE")
        fullscreen_atom = self._display.intern_atom("_NET_WM_STATE_FULLSCREEN")
        root = self._display.screen().root

        action = 1 if enabled else 0  # _NET_WM_STATE_ADD or _REMOVE

        event = _create_client_message_event(
            self._display,
            self._xwindow,
            net_wm_state,
            [action, fullscreen_atom, 0, 1, 0],
        )
        root.send_event(
            event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask
        )
        self._display.flush()

    def set_state(self, state: str) -> None:
        """Set a _NET_WM_STATE property (e.g. 'maximized_vert')."""
        net_wm_state = self._display.intern_atom("_NET_WM_STATE")
        state_atom = self._display.intern_atom(f"_NET_WM_STATE_{state.upper()}")
        root = self._display.screen().root

        event = _create_client_message_event(
            self._display,
            self._xwindow,
            net_wm_state,
            [1, state_atom, 0, 1, 0],  # _NET_WM_STATE_ADD
        )
        root.send_event(
            event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask
        )
        self._display.flush()

    def screenshot(self, path: str | None = None) -> Image.Image:
        """Capture a screenshot of this window."""
        geo = self._xwindow.get_geometry()
        raw = self._xwindow.get_image(
            0, 0, geo.width, geo.height, X.ZPixmap, 0xFFFFFFFF
        )
        image = Image.frombytes(
            "RGBX", (geo.width, geo.height), raw.data, "raw", "BGRX"
        )
        image = image.convert("RGB")
        if path:
            image.save(path)
        return image

    def __eq__(self, other):
        if isinstance(other, Window):
            return self._xwindow.id == other._xwindow.id
        return NotImplemented

    def __hash__(self):
        return hash(self._xwindow.id)

    def __repr__(self):
        return f"Window(id=0x{self._xwindow.id:x}, title={self.title!r})"


class _CloseButtonProxy:
    """Proxy representing the close button area on a frame's titlebar.

    When a mouse click targets this, it clicks near the top-right corner
    of the frame window where close buttons typically reside.
    """

    def __init__(self, frame_window: Window):
        self._frame = frame_window

    @property
    def position(self) -> tuple[int, int]:
        geo = self._frame.geometry
        # Close button is typically near top-right of the frame
        return (geo.x + geo.width - 10, geo.y + 10)


def Xlib_client_message(display, window, message_type, data):
    """Create a ClientMessage event for WM_PROTOCOLS."""
    from Xlib.protocol import event

    return event.ClientMessage(
        window=window,
        client_type=message_type,
        data=(32, data + [0] * (5 - len(data))),
    )


def _create_client_message_event(display, window, message_type, data):
    """Create a ClientMessage event for _NET_WM_STATE changes."""
    from Xlib.protocol import event

    return event.ClientMessage(
        window=window,
        client_type=message_type,
        data=(32, data + [0] * (5 - len(data))),
    )
