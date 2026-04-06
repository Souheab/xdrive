"""Tests for VirtualDisplay."""

import os

import pytest

from xdrive.display import VirtualDisplay


class TestVirtualDisplay:
    def test_start_and_stop(self):
        display = VirtualDisplay(width=800, height=600)
        display.start()
        assert display.is_running
        assert display.name.startswith(":")
        display.stop()
        assert not display.is_running

    def test_context_manager(self):
        with VirtualDisplay(width=640, height=480) as display:
            assert display.is_running
            name = display.name
            assert name.startswith(":")
        assert not display.is_running

    def test_name_raises_before_start(self):
        display = VirtualDisplay()
        with pytest.raises(RuntimeError, match="not started"):
            _ = display.name

    def test_double_start_raises(self):
        display = VirtualDisplay(width=640, height=480)
        display.start()
        try:
            with pytest.raises(RuntimeError, match="already started"):
                display.start()
        finally:
            display.stop()

    def test_custom_dimensions(self):
        with VirtualDisplay(width=1024, height=768) as display:
            assert display.width == 1024
            assert display.height == 768

    def test_display_socket_exists_while_running(self):
        with VirtualDisplay(width=640, height=480) as display:
            num = display.name.lstrip(":")
            socket_path = f"/tmp/.X11-unix/X{num}"
            assert os.path.exists(socket_path), f"Expected X11 socket at {socket_path}"

    def test_not_running_before_start(self):
        display = VirtualDisplay()
        assert not display.is_running
