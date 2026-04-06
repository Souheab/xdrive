"""Integration tests for XDrive window creation and screen queries."""

import pytest

from xdrive import XDrive, expect
from xdrive.geometry import Geometry
from xdrive.window import Window


class TestWindowCreation:
    def test_new_window_is_mapped(self, xd):
        win = xd.new_window(title="Test Window")
        assert win.is_mapped

    def test_new_window_title(self, xd):
        win = xd.new_window(title="Hello xdrive")
        assert win.title == "Hello xdrive"

    def test_new_window_size(self, xd):
        win = xd.new_window(title="Sized", size=(320, 240))
        geo = win.geometry
        assert geo.width == 320
        assert geo.height == 240

    def test_new_window_position(self, xd):
        win = xd.new_window(title="Positioned", size=(200, 100), position=(50, 60))
        geo = win.geometry
        assert geo.x == 50
        assert geo.y == 60

    def test_new_window_repr(self, xd):
        win = xd.new_window(title="ReprTest")
        r = repr(win)
        assert "Window" in r
        assert "ReprTest" in r

    def test_new_window_has_unique_id(self, xd):
        win1 = xd.new_window(title="Win1")
        win2 = xd.new_window(title="Win2")
        assert win1.id != win2.id

    def test_window_equality(self, xd):
        win = xd.new_window(title="EqTest")
        # A window is equal to itself
        assert win == win

    def test_window_hash(self, xd):
        win = xd.new_window(title="HashTest")
        s = {win}
        assert win in s


class TestWindowProperties:
    def test_set_title(self, xd):
        win = xd.new_window(title="Original")
        win.set_title("Updated")
        assert win.title == "Updated"

    def test_set_size(self, xd):
        win = xd.new_window(title="Resizable", size=(400, 300))
        win.set_size(500, 350)
        xd.wait_for_layout()
        geo = win.geometry
        assert geo.width == 500
        assert geo.height == 350

    def test_window_geometry_returns_geometry(self, xd):
        win = xd.new_window(title="GeoTest", size=(200, 150))
        assert isinstance(win.geometry, Geometry)

    def test_window_focus(self, xd):
        win = xd.new_window(title="FocusTest")
        win.focus()
        xd.wait_for_layout()
        assert win.is_focused

    def test_window_kill(self, xd):
        win = xd.new_window(title="KillTest")
        assert win.is_mapped
        win.kill()
        xd.wait_for_layout()
        # After kill the window should no longer appear in screen.windows()
        ids = [w.id for w in xd.screen.windows()]
        assert win.id not in ids


class TestScreenQueries:
    def test_screen_geometry(self, xd):
        geo = xd.screen.geometry
        assert isinstance(geo, Geometry)
        assert geo.width > 0
        assert geo.height > 0

    def test_screen_size_matches_virtual_display(self, xd, virtual_display):
        geo = xd.screen.geometry
        assert geo.width == virtual_display.width
        assert geo.height == virtual_display.height

    def test_screen_windows_returns_list(self, xd):
        xd.new_window(title="ListTest")
        windows = xd.screen.windows()
        assert isinstance(windows, list)
        assert len(windows) >= 1
        assert all(isinstance(w, Window) for w in windows)

    def test_screen_focused_window(self, xd):
        win = xd.new_window(title="FocusQueryTest")
        win.focus()
        xd.wait_for_layout()
        focused = xd.screen.focused_window()
        # focused_window may return the window or its frame
        assert focused is not None


class TestScreenshot:
    def test_display_screenshot_returns_image(self, xd, tmp_path):
        from PIL import Image

        img = xd.screenshot()
        assert isinstance(img, Image.Image)
        assert img.width > 0
        assert img.height > 0

    def test_display_screenshot_saved_to_path(self, xd, tmp_path):
        path = str(tmp_path / "screen.png")
        xd.screenshot(path=path)
        import os

        assert os.path.isfile(path)

    def test_display_screenshot_region(self, xd):
        from PIL import Image

        img = xd.screenshot(region=(0, 0, 200, 150))
        assert isinstance(img, Image.Image)
        assert img.width == 200
        assert img.height == 150

    def test_window_screenshot_returns_image(self, xd):
        from PIL import Image

        win = xd.new_window(title="ScreenshotWin", size=(200, 150))
        img = win.screenshot()
        assert isinstance(img, Image.Image)
        assert img.width == 200
        assert img.height == 150

    def test_window_screenshot_saved_to_path(self, xd, tmp_path):
        import os

        win = xd.new_window(title="SavedShot", size=(100, 80))
        path = str(tmp_path / "win.png")
        win.screenshot(path=path)
        assert os.path.isfile(path)


class TestExpectAssertions:
    def test_expect_window_to_be_mapped(self, xd):
        win = xd.new_window(title="ExpectMapped")
        expect(win).to_be_mapped()

    def test_expect_window_to_have_title(self, xd):
        win = xd.new_window(title="AssertTitle")
        expect(win).to_have_title("AssertTitle")

    def test_expect_window_to_have_geometry_width(self, xd):
        win = xd.new_window(title="GeoAssert", size=(300, 200))
        expect(win).to_have_geometry(width=300, height=200)

    def test_expect_screen_window_count(self, xd):
        before = len(xd.screen.windows())
        xd.new_window(title="CountWin1")
        xd.new_window(title="CountWin2")
        after = len(xd.screen.windows())
        assert after >= before + 2

    def test_expect_window_list_are_all_mapped(self, xd):
        win1 = xd.new_window(title="ListMapped1")
        win2 = xd.new_window(title="ListMapped2")
        expect([win1, win2]).are_all_mapped()

    def test_expect_window_list_no_overlap(self, xd):
        win1 = xd.new_window(title="NoOverlap1", size=(100, 100), position=(0, 0))
        win2 = xd.new_window(title="NoOverlap2", size=(100, 100), position=(200, 200))
        expect([win1, win2]).have_no_overlapping_geometry()

    def test_expect_image_to_match_itself(self, xd):
        from PIL import Image

        img = xd.screenshot()
        expect(img).to_match(img)

    def test_expect_image_not_to_match_different(self, xd):
        from PIL import Image

        # Create a white window so the screenshot is not all-black
        xd.new_window(title="WhiteWindow", size=(400, 300), position=(0, 0))
        img1 = xd.screenshot()
        # A solid red image should differ from a screenshot containing a white window
        img2 = Image.new("RGB", img1.size, (255, 0, 0))
        expect(img1).not_to_match(img2)

    def test_expect_invalid_type_raises(self, xd):
        with pytest.raises(TypeError):
            expect(42)
