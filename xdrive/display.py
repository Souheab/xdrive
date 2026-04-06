"""Virtual display management using Xvfb."""

import os
import signal
import subprocess
import tempfile
import time


class VirtualDisplay:
    """Wraps Xvfb to provide isolated virtual X11 displays for testing."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        depth: int = 24,
        screens: list[tuple[int, int]] | None = None,
    ):
        self._width = width
        self._height = height
        self._depth = depth
        self._screens = screens
        self._process: subprocess.Popen | None = None
        self._display_num: int | None = None
        self._name: str | None = None

    @property
    def name(self) -> str:
        if self._name is None:
            raise RuntimeError("Display not started")
        return self._name

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _find_free_display(self) -> int:
        """Find an unused display number."""
        for num in range(99, 200):
            lock_file = f"/tmp/.X{num}-lock"
            socket_file = f"/tmp/.X11-unix/X{num}"
            if not os.path.exists(lock_file) and not os.path.exists(socket_file):
                return num
        raise RuntimeError("Could not find a free display number")

    def start(self) -> "VirtualDisplay":
        if self._process is not None:
            raise RuntimeError("Display already started")

        self._display_num = self._find_free_display()
        self._name = f":{self._display_num}"

        cmd = ["Xvfb", self._name]

        if self._screens:
            for i, (w, h) in enumerate(self._screens):
                cmd += ["-screen", str(i), f"{w}x{h}x{self._depth}"]
            self._width = self._screens[0][0]
            self._height = self._screens[0][1]
        else:
            cmd += ["-screen", "0", f"{self._width}x{self._height}x{self._depth}"]

        cmd += ["-ac", "-nolisten", "tcp"]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for the display to become available
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            lock_file = f"/tmp/.X{self._display_num}-lock"
            if os.path.exists(lock_file):
                # Give Xvfb a moment to fully initialize
                time.sleep(0.1)
                return self
            if self._process.poll() is not None:
                raise RuntimeError(f"Xvfb exited with code {self._process.returncode}")
            time.sleep(0.05)

        raise RuntimeError("Xvfb did not start in time")

    def stop(self) -> None:
        if self._process is not None:
            self._process.send_signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
            self._process = None

    def __enter__(self) -> "VirtualDisplay":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def __str__(self) -> str:
        return self._name or "<not started>"

    def __repr__(self) -> str:
        return f"VirtualDisplay(name={self._name!r}, {self._width}x{self._height})"
