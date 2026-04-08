"""XDrive: main entry point for X11 WM automation."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from typing import TYPE_CHECKING

from PIL import Image
from Xlib import X, Xatom, display as xdisplay

from .display import VirtualDisplay
from .events import EventRecorder, wait_for_condition, wait_for_x_event
from .keyboard import Keyboard
from .mouse import Mouse
from .screen import Screen
from .ui_tree import build_ui_tree
from .window import Window


class XDrive:
    """Main controller for X11 window manager automation.

    ``XDrive`` connects to an X display (real or virtual), optionally
    starts a window manager, and exposes helpers for creating windows,
    injecting input, and taking screenshots.

    Args:
        wm: Shell command to start the window manager.  ``None`` to
            skip WM launch.
        display: An existing ``VirtualDisplay``, a DISPLAY string
            (e.g. ``':0'``), or ``None`` to read ``$DISPLAY``.
        virtual: If ``True``, spin up a private Xvfb display.
        screen_size: ``(width, height)`` to use when *virtual* is
            ``True``.

    Example:
        >>> with XDrive(wm="./mywm", virtual=True) as xd:
        ...     win = xd.new_window(title="test")
    """

    def __init__(
        self,
        wm: str | None = None,
        display: str | VirtualDisplay | None = None,
        virtual: bool = False,
        screen_size: tuple[int, int] = (1920, 1080),
    ):
        self._wm_cmd = wm
        self._wm_process: subprocess.Popen | None = None
        self._virtual = virtual
        self._screen_size = screen_size
        self._own_display: VirtualDisplay | None = None

        # Resolve display name
        if isinstance(display, VirtualDisplay):
            self._display_name = display.name
        elif isinstance(display, str):
            self._display_name = display
        elif virtual:
            self._display_name = None  # will be set in __enter__
        else:
            self._display_name = os.environ.get("DISPLAY", ":0")

        self._xdisplay: xdisplay.Display | None = None
        self._mouse: Mouse | None = None
        self._keyboard: Keyboard | None = None
        self._screen: Screen | None = None

    def _connect(self) -> None:
        """Connect to the X display and initialize sub-controllers."""
        self._xdisplay = xdisplay.Display(self._display_name)
        self._mouse = Mouse(self._xdisplay)
        self._keyboard = Keyboard(self._xdisplay)
        self._screen = Screen(self._xdisplay)

        # Select events on root window so we can receive SubstructureRedirect etc.
        root = self._xdisplay.screen().root
        root.change_attributes(
            event_mask=(
                X.SubstructureNotifyMask | X.PropertyChangeMask | X.FocusChangeMask
            )
        )
        self._xdisplay.flush()

    def _start_wm(self) -> None:
        """Start the window manager process."""
        if self._wm_cmd:
            env = os.environ.copy()
            env["DISPLAY"] = self._display_name
            self._wm_process = subprocess.Popen(
                self._wm_cmd,
                shell=True,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Give the WM time to start and grab the root window
            time.sleep(0.3)

    def _stop_wm(self) -> None:
        if self._wm_process:
            self._wm_process.send_signal(signal.SIGTERM)
            try:
                self._wm_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._wm_process.kill()
                self._wm_process.wait()
            self._wm_process = None

    @property
    def mouse(self) -> Mouse:
        """The :class:`~xdrive.mouse.Mouse` input controller.

        Raises:
            AssertionError: If ``XDrive`` has not been entered as a
                context manager.
        """
        assert self._mouse is not None, "XDrive not connected"
        return self._mouse

    @property
    def keyboard(self) -> Keyboard:
        """The :class:`~xdrive.keyboard.Keyboard` input controller.

        Raises:
            AssertionError: If ``XDrive`` has not been entered as a
                context manager.
        """
        assert self._keyboard is not None, "XDrive not connected"
        return self._keyboard

    @property
    def screen(self) -> Screen:
        """The :class:`~xdrive.screen.Screen` state accessor.

        Raises:
            AssertionError: If ``XDrive`` has not been entered as a
                context manager.
        """
        assert self._screen is not None, "XDrive not connected"
        return self._screen

    def new_window(
        self,
        title: str = "xdrive",
        size: tuple[int, int] = (640, 480),
        position: tuple[int, int] | None = None,
        type: str | None = None,
    ) -> Window:
        """Create and map a synthetic X11 test window.

        The window is fully mapped (and waited on) before returning.
        It sets ``WM_NAME``, ``_NET_WM_NAME``, ``WM_PROTOCOLS
        (WM_DELETE_WINDOW)``, and optionally ``_NET_WM_WINDOW_TYPE``.

        Args:
            title: Window title.
            size: ``(width, height)`` in pixels.
            position: ``(x, y)`` position, or ``None`` for the default.
            type: EWMH window type shorthand (``'dialog'``,
                ``'splash'``, ``'dock'``, etc.).

        Returns:
            A :class:`~xdrive.window.Window` instance.

        Example:
            >>> win = xd.new_window(title="hello", size=(400, 300))
        """
        root = self._xdisplay.screen().root
        screen = self._xdisplay.screen()

        # Window type atom
        window_type_atom = None
        override_redirect = False
        if type:
            type_map = {
                "dialog": "_NET_WM_WINDOW_TYPE_DIALOG",
                "splash": "_NET_WM_WINDOW_TYPE_SPLASH",
                "dock": "_NET_WM_WINDOW_TYPE_DOCK",
                "toolbar": "_NET_WM_WINDOW_TYPE_TOOLBAR",
                "utility": "_NET_WM_WINDOW_TYPE_UTILITY",
                "menu": "_NET_WM_WINDOW_TYPE_MENU",
                "notification": "_NET_WM_WINDOW_TYPE_NOTIFICATION",
                "normal": "_NET_WM_WINDOW_TYPE_NORMAL",
            }
            atom_name = type_map.get(type)
            if atom_name:
                window_type_atom = self._xdisplay.intern_atom(atom_name)
            if type in ("splash", "dock"):
                override_redirect = True

        x = position[0] if position else 0
        y = position[1] if position else 0
        w, h = size

        xwindow = root.create_window(
            x,
            y,
            w,
            h,
            border_width=0,
            depth=screen.root_depth,
            window_class=X.InputOutput,
            visual=X.CopyFromParent,
            colormap=X.CopyFromParent,
            background_pixel=screen.white_pixel,
            event_mask=(
                X.ExposureMask
                | X.StructureNotifyMask
                | X.FocusChangeMask
                | X.PropertyChangeMask
            ),
            override_redirect=override_redirect,
        )

        # Set window title
        net_wm_name = self._xdisplay.intern_atom("_NET_WM_NAME")
        utf8_string = self._xdisplay.intern_atom("UTF8_STRING")
        xwindow.change_property(net_wm_name, utf8_string, 8, title.encode("utf-8"))
        xwindow.change_property(
            Xatom.WM_NAME, Xatom.STRING, 8, title.encode("latin-1", errors="replace")
        )

        # Set WM_PROTOCOLS (WM_DELETE_WINDOW)
        wm_protocols = self._xdisplay.intern_atom("WM_PROTOCOLS")
        wm_delete = self._xdisplay.intern_atom("WM_DELETE_WINDOW")
        xwindow.change_property(wm_protocols, Xatom.ATOM, 32, [wm_delete])

        # Set window type
        if window_type_atom:
            net_wm_type = self._xdisplay.intern_atom("_NET_WM_WINDOW_TYPE")
            xwindow.change_property(net_wm_type, Xatom.ATOM, 32, [window_type_atom])

        # Set size hints
        from Xlib import Xutil

        flags = Xutil.USSize
        if position:
            flags |= Xutil.USPosition
        xwindow.set_wm_normal_hints(
            flags=flags,
            min_width=w,
            min_height=h,
        )

        # Map the window
        xwindow.map()
        self._xdisplay.flush()

        win = Window(xwindow, self._xdisplay)

        # Wait for the window to be mapped
        try:
            self.wait_for(lambda: win.is_mapped, timeout=3.0)
        except TimeoutError:
            pass

        # Small delay for WM to process
        time.sleep(0.1)

        return win

    def launch(self, command: str) -> Window:
        """Launch a real application and return its first new window.

        Sets ``DISPLAY`` in the child process environment and waits
        up to 10 seconds for a new window to appear.

        Args:
            command: Shell command to execute.

        Returns:
            The newly created :class:`~xdrive.window.Window`.

        Raises:
            RuntimeError: If no new window appears within the timeout.

        Example:
            >>> win = xd.launch("xterm")
        """
        before_windows = set(w.id for w in self.screen.windows())

        env = os.environ.copy()
        env["DISPLAY"] = self._display_name
        subprocess.Popen(
            command,
            shell=True,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for a new window to appear
        def new_window_appeared():
            current = set(w.id for w in self.screen.windows())
            return len(current - before_windows) > 0

        self.wait_for(new_window_appeared, timeout=10.0)
        time.sleep(0.2)

        current = self.screen.windows()
        current_ids = set(w.id for w in current)
        new_ids = current_ids - before_windows
        for win in current:
            if win.id in new_ids:
                return win

        raise RuntimeError(f"No new window appeared after launching {command!r}")

    def screenshot(
        self,
        path: str | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> Image.Image:
        """Capture a screenshot of the root window (full display).

        Reads the root window pixmap in ZPixmap/BGRX format and
        converts to an RGB PIL ``Image``.

        Args:
            path: If given, save the image to this file path.
            region: Optional ``(x, y, width, height)`` sub-region.

        Returns:
            A PIL ``Image.Image`` in RGB mode.

        Example:
            >>> img = xd.screenshot("output/full.png")
        """
        root = self._xdisplay.screen().root
        geo = root.get_geometry()

        if region:
            rx, ry, rw, rh = region
        else:
            rx, ry, rw, rh = 0, 0, geo.width, geo.height

        raw = root.get_image(rx, ry, rw, rh, X.ZPixmap, 0xFFFFFFFF)
        image = Image.frombytes("RGBX", (rw, rh), raw.data, "raw", "BGRX")
        image = image.convert("RGB")

        if path:
            image.save(path)
        return image

    def ui_tree(self):
        """Build and return a :class:`~xdrive.ui_tree.UITree` snapshot.

        Returns:
            A :class:`~xdrive.ui_tree.UITree` representing the current
            X11 window hierarchy.
        """
        return build_ui_tree(self._xdisplay)

    def wait_for(
        self,
        condition,
        timeout: float = 5.0,
    ) -> None:
        """Wait for a condition to become truthy.

        Polls *condition* (a callable or value) with a short interval
        until it evaluates to ``True`` or the timeout expires.

        Args:
            condition: A zero-argument callable returning a bool, or
                any value that will be tested for truthiness.
            timeout: Maximum wait time in seconds.

        Raises:
            TimeoutError: If the condition is not met.

        Example:
            >>> xd.wait_for(lambda: win.is_mapped, timeout=3.0)
        """
        if callable(condition):
            wait_for_condition(condition, timeout=timeout)
        else:
            # Try treating it as a truthy value check
            wait_for_condition(lambda: bool(condition), timeout=timeout)

    def wait_for_event(
        self,
        event_name: str,
        window: Window | None = None,
        timeout: float = 5.0,
    ) -> None:
        """Wait for a named X11 event on the display connection.

        Args:
            event_name: X11 event name (e.g. ``'MapNotify'``).
            window: Restrict to events for this window.
            timeout: Maximum wait time in seconds.

        Raises:
            TimeoutError: If the event is not received in time.
        """
        wait_for_x_event(self._xdisplay, event_name, window=window, timeout=timeout)

    def wait_for_layout(self, timeout: float = 3.0) -> None:
        """Wait for layout to stabilise.

        Sleeps briefly and drains all pending X events, giving the
        window manager time to finish processing ``ConfigureNotify``
        and related layout events.

        Args:
            timeout: Not actively polled; reserved for future use.
        """
        time.sleep(0.5)
        # Drain any pending events
        while self._xdisplay.pending_events():
            self._xdisplay.next_event()

    @contextlib.contextmanager
    def record_events(self):
        """Context manager that records X11 events for later assertion.

        Yields an :class:`~xdrive.events.EventRecorder`.  Recording
        starts on entry and stops on exit.

        Example:
            >>> with xd.record_events() as rec:
            ...     win = xd.new_window()
            >>> rec.assert_received("MapNotify")
        """
        recorder = EventRecorder(self._xdisplay)
        recorder.start()
        try:
            yield recorder
        finally:
            # Give events time to arrive
            time.sleep(0.1)
            recorder.stop()

    def __enter__(self) -> XDrive:
        if self._virtual:
            self._own_display = VirtualDisplay(
                width=self._screen_size[0],
                height=self._screen_size[1],
            )
            self._own_display.start()
            self._display_name = self._own_display.name

        self._connect()
        self._start_wm()
        return self

    def __exit__(self, *args) -> None:
        self._stop_wm()
        if self._xdisplay:
            self._xdisplay.close()
            self._xdisplay = None
        if self._own_display:
            self._own_display.stop()
            self._own_display = None
