"""Pytest fixtures for xdrive."""

import pytest

from .display import VirtualDisplay
from .xdrive import XDrive


@pytest.fixture(scope="session")
def virtual_display():
    """Provide a session-scoped Xvfb virtual display.

    The display is started once per test session and shared by all
    tests.  Resolution defaults to 1920×1080.

    Yields:
        A running :class:`~xdrive.display.VirtualDisplay`.

    Example:
        >>> def test_something(virtual_display):
        ...     print(virtual_display.name)  # ':99'
    """
    with VirtualDisplay(width=1920, height=1080) as display:
        yield display


@pytest.fixture
def xd(virtual_display):
    """Provide a per-test XDrive instance on the session virtual display.

    Override ``wm=`` by parametrizing or defining your own fixture.
    """
    with XDrive(display=virtual_display) as xd:
        yield xd
