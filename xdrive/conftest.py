"""Pytest fixtures for xdrive."""

import pytest

from .display import VirtualDisplay
from .xdrive import XDrive


@pytest.fixture(scope="session")
def virtual_display():
    """Session-scoped virtual display."""
    with VirtualDisplay(width=1920, height=1080) as display:
        yield display


@pytest.fixture
def xd(virtual_display):
    """Per-test XDrive instance connected to the session virtual display.

    Override wm= by parametrizing or defining your own fixture.
    """
    with XDrive(display=virtual_display) as xd:
        yield xd
