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

    Usage:
        # Connect to an existing display
        with XDrive(wm="./mywm", display=":0") as xd:
            ...

        # Spin up a virtual display
        with XDrive(wm="./mywm", virtual=True, screen_size=(1920, 1080)) as xd:
            ...
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
        assert self._mouse is not None, "XDrive not connected"
        return self._mouse

    @property
    def keyboard(self) -> Keyboard:
        assert self._keyboard is not None, "XDrive not connected"
        return self._keyboard

    @property
    def screen(self) -> Screen:
        assert self._screen is not None, "XDrive not connected"
        return self._screen

    def new_window(
        self,
        title: str = "xdrive",
        size: tuple[int, int] = (640, 480),
        position: tuple[int, int] | None = None,
        type: str | None = None,
    ) -> Window:
        """Create a synthetic X11 test window."""
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
        """Launch a real application and return its window."""
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
        """Take a screenshot of the entire display or a region."""
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
        """Build and return a UI tree snapshot."""
        return build_ui_tree(self._xdisplay)

    def wait_for(
        self,
        condition,
        timeout: float = 5.0,
    ) -> None:
        """Wait for a condition to become true.

        condition can be a callable or a property that evaluates to bool.
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
        """Wait for a specific X11 event."""
        wait_for_x_event(self._xdisplay, event_name, window=window, timeout=timeout)

    def wait_for_layout(self, timeout: float = 3.0) -> None:
        """Wait for layout to stabilize (no ConfigureNotify events for a period)."""
        time.sleep(0.5)
        # Drain any pending events
        while self._xdisplay.pending_events():
            self._xdisplay.next_event()

    @contextlib.contextmanager
    def record_events(self):
        """Context manager to record X11 events."""
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
