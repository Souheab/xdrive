"""xdrive: X11 window manager automation and testing."""

from .assertions import expect
from .display import VirtualDisplay
from .geometry import Geometry
from .xdrive import XDrive

__all__ = [
    "XDrive",
    "VirtualDisplay",
    "Geometry",
    "expect",
]
