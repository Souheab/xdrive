"""Screen state queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image
from Xlib import X, Xatom

from .geometry import Geometry
from .window import Window

if TYPE_CHECKING:
    from Xlib.display import Display


class Screen:
    """Provides queries about the current screen/display state."""

    def __init__(self, display: Display):
        self._display = display

    @property
    def geometry(self) -> Geometry:
        root = self._display.screen().root
        geo = root.get_geometry()
        return Geometry(x=0, y=0, width=geo.width, height=geo.height)

    def windows(self) -> list[Window]:
        """Return all managed (mapped, non-override-redirect) top-level windows."""
        root = self._display.screen().root

        # Try _NET_CLIENT_LIST first
        net_client_list = self._display.intern_atom("_NET_CLIENT_LIST")
        prop = root.get_full_property(net_client_list, Xatom.WINDOW)
        if prop and prop.value:
            result = []
            for wid in prop.value:
                try:
                    xwin = self._display.create_resource_object("window", wid)
                    result.append(Window(xwin, self._display))
                except Exception:
                    pass
            return result

        # Fall back to querying children of root
        children = root.query_tree().children
        result = []
        for child in children:
            try:
                attrs = child.get_attributes()
                if attrs.map_state != X.IsUnmapped and not attrs.override_redirect:
                    result.append(Window(child, self._display))
            except Exception:
                pass
        return result

    def focused_window(self) -> Window | None:
        """Return the currently focused window, or None."""
        focused = self._display.get_input_focus().focus
        if hasattr(focused, "id"):
            root = self._display.screen().root
            if focused.id == root.id:
                return None
            return Window(focused, self._display)
        return None

    def window_at(self, x: int, y: int) -> Window | None:
        """Return the window under the given coordinates."""
        root = self._display.screen().root
        # Use translate_coords to find the child at position
        result = root.query_pointer()
        # Actually query which child is at the coordinates
        child = root.query_pointer().child
        if child and hasattr(child, "id") and child.id != 0:
            return Window(
                self._display.create_resource_object("window", child.id),
                self._display,
            )

        # Manual approach: check all top-level children
        children = root.query_tree().children
        for win in reversed(children):  # back-to-front
            try:
                geo_data = win.get_geometry()
                attrs = win.get_attributes()
                if attrs.map_state == X.IsUnmapped:
                    continue
                # Translate to root coords
                try:
                    translated = win.translate_coords(root, 0, 0)
                    wx, wy = -translated.x, -translated.y
                except Exception:
                    wx, wy = geo_data.x, geo_data.y
                if wx <= x < wx + geo_data.width and wy <= y < wy + geo_data.height:
                    return Window(win, self._display)
            except Exception:
                pass
        return None

    def window_tree(self) -> dict:
        """Return the full X11 window hierarchy as a nested dict."""
        root = self._display.screen().root
        return self._build_tree(root)

    def _build_tree(self, window) -> dict:
        try:
            geo = window.get_geometry()
            name_prop = window.get_full_property(Xatom.WM_NAME, Xatom.STRING)
            name = ""
            if name_prop and name_prop.value:
                val = name_prop.value
                name = val.decode("latin-1") if isinstance(val, bytes) else str(val)
        except Exception:
            geo = None
            name = ""

        children = []
        try:
            for child in window.query_tree().children:
                children.append(self._build_tree(child))
        except Exception:
            pass

        node = {
            "id": window.id,
            "name": name,
            "children": children,
        }
        if geo:
            node["geometry"] = {
                "x": geo.x,
                "y": geo.y,
                "width": geo.width,
                "height": geo.height,
            }
        return node
