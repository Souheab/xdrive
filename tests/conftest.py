"""Shared pytest fixtures for xdrive tests."""

import pytest

from xdrive import VirtualDisplay, XDrive


@pytest.fixture(scope="session")
def virtual_display():
    """Session-scoped virtual Xvfb display shared across all tests."""
    with VirtualDisplay(width=1280, height=800) as display:
        yield display


@pytest.fixture
def xd(virtual_display):
    """Per-test XDrive instance connected to the session virtual display."""
    with XDrive(display=virtual_display) as xd:
        yield xd
