"""Assertion helpers inspired by Playwright's expect()."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from .geometry import Geometry

if TYPE_CHECKING:
    from .screen import Screen
    from .window import Window


class WindowExpectation:
    """Fluent assertions on a :class:`~xdrive.window.Window`.

    Obtained via ``expect(window)``.

    Args:
        window: The window to assert against.
    """

    def __init__(self, window: Window):
        self._window = window

    def to_be_mapped(self) -> None:
        """Assert the window is mapped (visible on the display).

        Raises:
            AssertionError: If the window is unmapped.
        """
        assert self._window.is_mapped, f"Expected window {self._window!r} to be mapped"

    def not_to_be_mapped(self) -> None:
        """Assert the window is **not** mapped.

        Raises:
            AssertionError: If the window is mapped.
        """
        assert (
            not self._window.is_mapped
        ), f"Expected window {self._window!r} NOT to be mapped"

    def to_be_focused(self) -> None:
        """Assert the window holds input focus.

        Raises:
            AssertionError: If the window is not focused.
        """
        assert (
            self._window.is_focused
        ), f"Expected window {self._window!r} to be focused"

    def to_be_fullscreen(self) -> None:
        """Assert ``_NET_WM_STATE_FULLSCREEN`` is set.

        Raises:
            AssertionError: If the window is not fullscreen.
        """
        assert (
            self._window.is_fullscreen
        ), f"Expected window {self._window!r} to be fullscreen"

    def to_have_title(self, title: str) -> None:
        """Assert the window title matches exactly.

        Args:
            title: Expected title string.

        Raises:
            AssertionError: If the title differs.
        """
        actual = self._window.title
        assert actual == title, f"Expected title {title!r}, got {actual!r}"

    def to_have_geometry(
        self,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        """Assert specific geometry fields.

        Only the provided keyword arguments are checked; the rest are
        ignored.

        Args:
            x: Expected x position.
            y: Expected y position.
            width: Expected width.
            height: Expected height.

        Raises:
            AssertionError: If any provided field doesn't match.
        """
        geo = self._window.geometry
        if x is not None:
            assert geo.x == x, f"Expected x={x}, got {geo.x}"
        if y is not None:
            assert geo.y == y, f"Expected y={y}, got {geo.y}"
        if width is not None:
            assert geo.width == width, f"Expected width={width}, got {geo.width}"
        if height is not None:
            assert geo.height == height, f"Expected height={height}, got {geo.height}"

    def not_to_have_geometry(self, geometry: Geometry) -> None:
        """Assert the window geometry differs from *geometry*.

        Args:
            geometry: The geometry that should **not** match.

        Raises:
            AssertionError: If the geometry matches exactly.
        """
        actual = self._window.geometry
        assert (
            actual != geometry
        ), f"Expected geometry to differ from {geometry}, but got the same"

    def to_be_reparented(self) -> None:
        """Assert the window has been reparented into a WM frame.

        Raises:
            AssertionError: If the window's frame is itself.
        """
        frame = self._window.frame
        assert (
            frame.id != self._window.id
        ), f"Expected window {self._window!r} to be reparented (have a frame)"

    def to_have_frame(self) -> None:
        """Alias for :meth:`to_be_reparented`."""
        self.to_be_reparented()

    def to_match_screenshot(self, baseline_path: str, threshold: float = 0.99) -> None:
        """Assert the window screenshot matches a baseline image.

        Args:
            baseline_path: Path to the baseline PNG file.
            threshold: Minimum pixel-level similarity (0.0–1.0).

        Raises:
            AssertionError: If the images differ beyond *threshold*
                or have different sizes.
        """
        baseline = Image.open(baseline_path)
        current = self._window.screenshot()

        if baseline.size != current.size:
            raise AssertionError(
                f"Screenshot size mismatch: baseline={baseline.size}, "
                f"current={current.size}"
            )

        similarity = _image_similarity(baseline, current)
        assert (
            similarity >= threshold
        ), f"Screenshot similarity {similarity:.4f} < threshold {threshold}"

    def to_have_color_at(self, x: int, y: int, color: str) -> None:
        """Assert the pixel colour at ``(x, y)`` matches *color*.

        Args:
            x: Horizontal pixel coordinate within the window.
            y: Vertical pixel coordinate within the window.
            color: Expected colour as a lowercase hex string
                (e.g. ``'#ff0000'``).

        Raises:
            AssertionError: If the colour does not match.
        """
        img = self._window.screenshot()
        r, g, b = img.getpixel((x, y))[:3]
        actual_hex = f"#{r:02x}{g:02x}{b:02x}"
        expected = color.lower()
        assert (
            actual_hex == expected
        ), f"Expected color {expected} at ({x},{y}), got {actual_hex}"


class ScreenExpectation:
    """Fluent assertions on a :class:`~xdrive.screen.Screen`.

    Obtained via ``expect(screen)``.

    Args:
        screen: The screen to assert against.
    """

    def __init__(self, screen: Screen):
        self._screen = screen

    def to_have_n_windows(self, n: int) -> None:
        """Assert the number of managed top-level windows.

        Args:
            n: Expected window count.

        Raises:
            AssertionError: If the count differs.
        """
        actual = len(self._screen.windows())
        assert actual == n, f"Expected {n} windows, got {actual}"

    def focused_window(self) -> _FocusedWindowExpectation:
        """Return a sub-expectation for the currently focused window."""
        return _FocusedWindowExpectation(self._screen)


class _FocusedWindowExpectation:
    """Sub-expectation for asserting which window is focused."""

    def __init__(self, screen: Screen):
        self._screen = screen

    def to_be(self, window: Window) -> None:
        """Assert that *window* is the currently focused window.

        Args:
            window: Expected focused window.

        Raises:
            AssertionError: If no window or a different window is focused.
        """
        focused = self._screen.focused_window()
        assert focused is not None, "No window is focused"
        assert (
            focused.id == window.id
        ), f"Expected focused window to be {window!r}, got {focused!r}"


class ImageExpectation:
    """Fluent assertions on a PIL ``Image``.

    Obtained via ``expect(image)``.

    Args:
        image: The PIL image to assert against.
    """

    def __init__(self, image: Image.Image):
        self._image = image

    def not_to_match(self, other: Image.Image) -> None:
        """Assert this image is visually different from *other*.

        Args:
            other: Image to compare against.

        Raises:
            AssertionError: If the images are similar (>= 99 %).
        """
        if self._image.size != other.size:
            return  # Different sizes = not matching
        similarity = _image_similarity(self._image, other)
        assert (
            similarity < 0.99
        ), f"Expected images to differ, but similarity is {similarity:.4f}"

    def to_match(self, other: Image.Image, threshold: float = 0.99) -> None:
        """Assert this image matches *other* above *threshold*.

        Args:
            other: Image to compare against.
            threshold: Minimum pixel similarity (0.0–1.0).

        Raises:
            AssertionError: If the images differ or have different sizes.
        """
        if self._image.size != other.size:
            raise AssertionError(
                f"Image size mismatch: {self._image.size} vs {other.size}"
            )
        similarity = _image_similarity(self._image, other)
        assert (
            similarity >= threshold
        ), f"Image similarity {similarity:.4f} < threshold {threshold}"


class WindowListExpectation:
    """Fluent assertions on a list of :class:`~xdrive.window.Window` objects.

    Obtained via ``expect([win1, win2, ...])``.

    Args:
        windows: The list of windows to assert against.
    """

    def __init__(self, windows: list[Window]):
        self._windows = windows

    def have_no_overlapping_geometry(self) -> None:
        """Assert that no two windows in the list overlap.

        Raises:
            AssertionError: If any pair of windows overlaps.
        """
        geos = [w.geometry for w in self._windows]
        for i in range(len(geos)):
            for j in range(i + 1, len(geos)):
                assert not geos[i].overlaps(geos[j]), (
                    f"Windows overlap: {self._windows[i]!r} ({geos[i]}) "
                    f"and {self._windows[j]!r} ({geos[j]})"
                )

    def are_all_mapped(self) -> None:
        """Assert every window in the list is mapped.

        Raises:
            AssertionError: If any window is unmapped.
        """
        for win in self._windows:
            assert win.is_mapped, f"Window {win!r} is not mapped"

    def tile_covers(self, screen, gaps: int = 0) -> None:
        """Assert that the windows tile-cover at least 95 % of the screen.

        Args:
            screen: A :class:`~xdrive.screen.Screen` to measure against.
            gaps: Pixel gap size between tiles (used to compute a
                tolerance allowance).

        Raises:
            AssertionError: If the combined window area (plus gap
                allowance) is less than 95 % of the screen area.
        """
        screen_geo = screen.geometry
        total_screen = screen_geo.width * screen_geo.height

        # Sum up window areas (accounting for gaps)
        total_window = 0
        for win in self._windows:
            geo = win.geometry
            total_window += geo.width * geo.height

        # Allow for gaps between windows
        n = len(self._windows)
        gap_allowance = gaps * (n + 1) * max(screen_geo.width, screen_geo.height)

        assert total_window + gap_allowance >= total_screen * 0.95, (
            f"Windows do not cover screen: window_area={total_window}, "
            f"screen_area={total_screen}, gap_allowance={gap_allowance}"
        )


def expect(target):
    """Create a fluent expectation object for *target*.

    Dispatches to the appropriate expectation class based on the type
    of *target*.

    Args:
        target: A :class:`~xdrive.window.Window`,
            :class:`~xdrive.screen.Screen`, PIL ``Image``, or a
            ``list`` of windows.

    Returns:
        An expectation object with assertion methods.

    Raises:
        TypeError: If *target* is an unsupported type.

    Example:
        >>> expect(window).to_be_mapped()
        >>> expect(screen).to_have_n_windows(3)
        >>> expect([win1, win2]).have_no_overlapping_geometry()
    """
    from .screen import Screen
    from .window import Window

    if isinstance(target, Window):
        return WindowExpectation(target)
    elif isinstance(target, Screen):
        return ScreenExpectation(target)
    elif isinstance(target, Image.Image):
        return ImageExpectation(target)
    elif isinstance(target, list):
        return WindowListExpectation(target)
    else:
        raise TypeError(f"Cannot create expectation for {type(target)}")


def _image_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Compute pixel-level similarity between two images.

    Each pixel pair is considered matching if every RGB channel
    differs by at most 5.

    Args:
        img1: First image.
        img2: Second image.

    Returns:
        A float between 0.0 (completely different) and 1.0 (identical).
    """
    if img1.size != img2.size:
        return 0.0

    pixels1 = list(img1.getdata())
    pixels2 = list(img2.getdata())

    if len(pixels1) == 0:
        return 1.0

    matching = 0
    for p1, p2 in zip(pixels1, pixels2):
        # Compare RGB channels
        r1, g1, b1 = p1[:3]
        r2, g2, b2 = p2[:3]
        if abs(r1 - r2) <= 5 and abs(g1 - g2) <= 5 and abs(b1 - b2) <= 5:
            matching += 1

    return matching / len(pixels1)
