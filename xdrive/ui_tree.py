"""UI tree: semantic snapshot of the WM state."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from Xlib import Xatom

from .geometry import Geometry

if TYPE_CHECKING:
    from Xlib.display import Display


@dataclass
class UINode:
    """A node in the UI tree."""

    xid: int
    geometry: Geometry
    properties: dict = field(default_factory=dict)
    children: list[UINode] = field(default_factory=list)
    parent: UINode | None = field(default=None, repr=False)
    node_type: str = ""  # "root", "frame", "titlebar", "client"

    @property
    def frame(self) -> UINode | None:
        if self.node_type == "frame":
            return self
        if self.parent and self.parent.node_type == "frame":
            return self.parent
        return None

    @property
    def client(self) -> UINode | None:
        if self.node_type == "client":
            return self
        for child in self.children:
            if child.node_type == "client":
                return child
        return None

    def __repr__(self):
        label = self.properties.get("wm_name", self.properties.get("title", ""))
        return f"UINode(xid=0x{self.xid:x}, type={self.node_type!r}, title={label!r})"


class UITree:
    """Semantic snapshot of the full X11/WM state as a traversable tree."""

    def __init__(self, root: UINode, all_nodes: list[UINode]):
        self._root = root
        self._all_nodes = all_nodes

    @property
    def root(self) -> UINode:
        return self._root

    def windows(self) -> list[UINode]:
        """Return all client window nodes."""
        return [n for n in self._all_nodes if n.node_type == "client"]

    def focused(self) -> UINode | None:
        """Return the focused window node, if any."""
        for node in self._all_nodes:
            state = node.properties.get("_NET_WM_STATE", [])
            if "_NET_WM_STATE_FOCUSED" in state:
                return node
        return None

    def find(
        self, *, wm_class: str | None = None, title: str | None = None
    ) -> UINode | None:
        """Find a node by wm_class or title."""
        for node in self._all_nodes:
            if wm_class and node.properties.get("wm_class") == wm_class:
                return node
            if title and node.properties.get("wm_name") == title:
                return node
            if title and node.properties.get("title") == title:
                return node
        return None

    def diff(self, other: UITree) -> UITreeDiff:
        """Compare two UI tree snapshots and return the differences."""
        before_map = {n.xid: n for n in self._all_nodes}
        after_map = {n.xid: n for n in other._all_nodes}

        added = [n for xid, n in after_map.items() if xid not in before_map]
        removed = [n for xid, n in before_map.items() if xid not in after_map]
        changed = []
        for xid in before_map:
            if xid in after_map:
                b = before_map[xid]
                a = after_map[xid]
                if b.geometry != a.geometry or b.properties != a.properties:
                    changed.append((b, a))

        return UITreeDiff(added=added, removed=removed, changed=changed)

    def __repr__(self):
        return f"UITree(windows={len(self.windows())})"


@dataclass
class UITreeDiff:
    added: list[UINode]
    removed: list[UINode]
    changed: list[tuple[UINode, UINode]]  # (before, after)

    def __repr__(self):
        return (
            f"UITreeDiff(added={len(self.added)}, "
            f"removed={len(self.removed)}, "
            f"changed={len(self.changed)})"
        )


def build_ui_tree(display: Display) -> UITree:
    """Build a UI tree from the current display state."""
    root_xwin = display.screen().root
    all_nodes: list[UINode] = []

    root_geo_data = root_xwin.get_geometry()
    root_node = UINode(
        xid=root_xwin.id,
        geometry=Geometry(0, 0, root_geo_data.width, root_geo_data.height),
        node_type="root",
    )
    all_nodes.append(root_node)

    # Get managed client list
    net_client_list = display.intern_atom("_NET_CLIENT_LIST")
    prop = root_xwin.get_full_property(net_client_list, Xatom.WINDOW)
    client_xids = set()
    if prop and prop.value:
        client_xids = set(prop.value)

    # Walk top-level children of root
    try:
        children = root_xwin.query_tree().children
    except Exception:
        children = []

    for child in children:
        try:
            _build_subtree(display, child, root_node, all_nodes, client_xids)
        except Exception:
            pass

    return UITree(root=root_node, all_nodes=all_nodes)


def _get_window_properties(display: Display, xwin) -> dict:
    """Extract key properties from an X window."""
    props = {}

    # WM_NAME
    try:
        net_wm_name = display.intern_atom("_NET_WM_NAME")
        utf8 = display.intern_atom("UTF8_STRING")
        p = xwin.get_full_property(net_wm_name, utf8)
        if p and p.value:
            val = p.value
            props["wm_name"] = (
                val.decode("utf-8") if isinstance(val, bytes) else str(val)
            )
        else:
            p = xwin.get_full_property(Xatom.WM_NAME, Xatom.STRING)
            if p and p.value:
                val = p.value
                props["wm_name"] = (
                    val.decode("latin-1") if isinstance(val, bytes) else str(val)
                )
    except Exception:
        pass

    # WM_CLASS
    try:
        p = xwin.get_full_property(Xatom.WM_CLASS, Xatom.STRING)
        if p and p.value:
            val = p.value
            if isinstance(val, bytes):
                parts = val.decode("latin-1").rstrip("\x00").split("\x00")
                props["wm_class"] = parts[-1] if parts else ""
            else:
                props["wm_class"] = str(val)
    except Exception:
        pass

    # _NET_WM_STATE
    try:
        net_wm_state = display.intern_atom("_NET_WM_STATE")
        p = xwin.get_full_property(net_wm_state, Xatom.ATOM)
        if p and p.value:
            atoms = p.value
            if isinstance(atoms, bytes):
                atoms = struct.unpack(f"{len(atoms)//4}I", atoms)
            state_names = []
            for atom in atoms:
                try:
                    state_names.append(display.get_atom_name(atom))
                except Exception:
                    state_names.append(str(atom))
            props["_NET_WM_STATE"] = state_names
        else:
            props["_NET_WM_STATE"] = []
    except Exception:
        props["_NET_WM_STATE"] = []

    # _NET_WM_WINDOW_TYPE
    try:
        net_wm_type = display.intern_atom("_NET_WM_WINDOW_TYPE")
        p = xwin.get_full_property(net_wm_type, Xatom.ATOM)
        if p and p.value:
            atoms = p.value
            if isinstance(atoms, bytes):
                atoms = struct.unpack(f"{len(atoms)//4}I", atoms)
            if atoms:
                try:
                    props["_NET_WM_WINDOW_TYPE"] = display.get_atom_name(atoms[0])
                except Exception:
                    props["_NET_WM_WINDOW_TYPE"] = str(atoms[0])
    except Exception:
        pass

    return props


def _build_subtree(display, xwin, parent_node, all_nodes, client_xids):
    """Recursively build UI tree nodes."""
    from Xlib import X

    try:
        geo = xwin.get_geometry()
        attrs = xwin.get_attributes()
    except Exception:
        return

    if attrs.map_state == X.IsUnmapped:
        return

    # Determine node type
    is_client = xwin.id in client_xids

    # Get properties
    props = _get_window_properties(display, xwin)

    try:
        translated = xwin.translate_coords(display.screen().root, 0, 0)
        abs_x, abs_y = -translated.x, -translated.y
    except Exception:
        abs_x, abs_y = geo.x, geo.y

    geometry = Geometry(abs_x, abs_y, geo.width, geo.height)

    if is_client:
        node_type = "client"
        props["title"] = props.get("wm_name", "")
    elif parent_node.node_type == "root" and not is_client:
        node_type = "frame"
    else:
        node_type = ""

    node = UINode(
        xid=xwin.id,
        geometry=geometry,
        properties=props,
        node_type=node_type,
        parent=parent_node,
    )
    parent_node.children.append(node)
    all_nodes.append(node)

    # Recurse into children
    try:
        children = xwin.query_tree().children
        for child in children:
            _build_subtree(display, child, node, all_nodes, client_xids)
    except Exception:
        pass
