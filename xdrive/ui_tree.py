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
    """A single node in the X11 window hierarchy snapshot.

    Each node corresponds to a mapped X window and carries its
    geometry, key properties, and pointers to parent/children.

    Attributes:
        xid: X11 window ID.
        geometry: Position and size as a :class:`~xdrive.geometry.Geometry`.
        properties: Dictionary of extracted X properties
            (``wm_name``, ``wm_class``, ``_NET_WM_STATE``, etc.).
        children: Child :class:`UINode` list.
        parent: Parent node, or ``None`` for the root.
        node_type: Role string: ``'root'``, ``'frame'``, ``'client'``,
            or ``''`` (unknown).
    """

    xid: int
    geometry: Geometry
    properties: dict = field(default_factory=dict)
    children: list[UINode] = field(default_factory=list)
    parent: UINode | None = field(default=None, repr=False)
    node_type: str = ""  # "root", "frame", "titlebar", "client"

    @property
    def frame(self) -> UINode | None:
        """Return the frame node for this window, or ``None``.

        If this node **is** a frame, returns *self*.  If the parent is
        a frame, returns the parent.
        """
        if self.node_type == "frame":
            return self
        if self.parent and self.parent.node_type == "frame":
            return self.parent
        return None

    @property
    def client(self) -> UINode | None:
        """Return the client child of this node, or ``None``.

        If this node itself is a client, returns *self*.
        """
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
    """Immutable snapshot of the X11 window hierarchy.

    Built by :func:`build_ui_tree`, the tree allows querying client
    windows, finding nodes by property, and diffing two snapshots to
    detect layout changes.

    Args:
        root: The root :class:`UINode`.
        all_nodes: Flat list of every node in the tree.

    Example:
        >>> tree = xd.ui_tree()
        >>> for node in tree.windows():
        ...     print(node)
    """

    def __init__(self, root: UINode, all_nodes: list[UINode]):
        self._root = root
        self._all_nodes = all_nodes

    @property
    def root(self) -> UINode:
        """The root window node."""
        return self._root

    def windows(self) -> list[UINode]:
        """Return all nodes whose ``node_type`` is ``'client'``.

        Returns:
            List of :class:`UINode` representing client windows.
        """
        return [n for n in self._all_nodes if n.node_type == "client"]

    def focused(self) -> UINode | None:
        """Return the focused client node, or ``None``.

        Checks for ``_NET_WM_STATE_FOCUSED`` in each node's properties.
        """
        for node in self._all_nodes:
            state = node.properties.get("_NET_WM_STATE", [])
            if "_NET_WM_STATE_FOCUSED" in state:
                return node
        return None

    def find(
        self, *, wm_class: str | None = None, title: str | None = None
    ) -> UINode | None:
        """Find the first node matching *wm_class* or *title*.

        Args:
            wm_class: Match against the ``wm_class`` property.
            title: Match against ``wm_name`` or ``title`` properties.

        Returns:
            The first matching :class:`UINode`, or ``None``.
        """
        for node in self._all_nodes:
            if wm_class and node.properties.get("wm_class") == wm_class:
                return node
            if title and node.properties.get("wm_name") == title:
                return node
            if title and node.properties.get("title") == title:
                return node
        return None

    def diff(self, other: UITree) -> UITreeDiff:
        """Compute the differences between this snapshot and *other*.

        Args:
            other: A newer :class:`UITree` snapshot.

        Returns:
            A :class:`UITreeDiff` with added, removed, and changed
            nodes.
        """
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
    """Result of comparing two :class:`UITree` snapshots.

    Attributes:
        added: Nodes present in the newer tree but not the older.
        removed: Nodes present in the older tree but not the newer.
        changed: List of ``(before, after)`` pairs for nodes whose
            geometry or properties differ.
    """

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
    """Build a :class:`UITree` snapshot from the current display state.

    Walks the X11 window hierarchy starting from the root, classifying
    each mapped window as ``'frame'`` or ``'client'`` based on
    ``_NET_CLIENT_LIST``.

    Args:
        display: An open ``Xlib.display.Display`` connection.

    Returns:
        A :class:`UITree` containing all mapped windows.
    """
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
    """Extract commonly used X properties from a window.

    Reads ``_NET_WM_NAME``, ``WM_NAME``, ``WM_CLASS``,
    ``_NET_WM_STATE``, and ``_NET_WM_WINDOW_TYPE``.

    Args:
        display: An open ``Xlib.display.Display``.
        xwin: An ``Xlib`` window object.

    Returns:
        A dict of property name → value mappings.
    """
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
