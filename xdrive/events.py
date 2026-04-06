"""Event waiting and recording."""

from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from Xlib import X

if TYPE_CHECKING:
    from Xlib.display import Display

    from .window import Window

# Map event type names to X11 event type constants
_EVENT_TYPE_MAP = {
    "KeyPress": X.KeyPress,
    "KeyRelease": X.KeyRelease,
    "ButtonPress": X.ButtonPress,
    "ButtonRelease": X.ButtonRelease,
    "MotionNotify": X.MotionNotify,
    "EnterNotify": X.EnterNotify,
    "LeaveNotify": X.LeaveNotify,
    "FocusIn": X.FocusIn,
    "FocusOut": X.FocusOut,
    "Expose": X.Expose,
    "DestroyNotify": X.DestroyNotify,
    "UnmapNotify": X.UnmapNotify,
    "MapNotify": X.MapNotify,
    "MapRequest": X.MapRequest,
    "ReparentNotify": X.ReparentNotify,
    "ConfigureNotify": X.ConfigureNotify,
    "ConfigureRequest": X.ConfigureRequest,
    "PropertyNotify": X.PropertyNotify,
    "ClientMessage": X.ClientMessage,
    "CreateNotify": X.CreateNotify,
}

# Reverse map
_EVENT_NAME_MAP = {v: k for k, v in _EVENT_TYPE_MAP.items()}


@dataclass
class RecordedEvent:
    """A recorded X11 event."""

    name: str
    event_type: int
    window_id: int | None = None
    timestamp: float = 0.0


class EventRecorder:
    """Records X11 events during a context for later assertion."""

    def __init__(self, display: Display):
        self._display = display
        self._events: list[RecordedEvent] = []
        self._recording = False
        self._thread: threading.Thread | None = None

    def _record_loop(self):
        """Background thread that polls for events."""
        while self._recording:
            count = self._display.pending_events()
            if count > 0:
                event = self._display.next_event()
                name = _EVENT_NAME_MAP.get(event.type, f"Unknown({event.type})")
                window_id = None
                if hasattr(event, "window") and hasattr(event.window, "id"):
                    window_id = event.window.id
                self._events.append(
                    RecordedEvent(
                        name=name,
                        event_type=event.type,
                        window_id=window_id,
                        timestamp=time.monotonic(),
                    )
                )
            else:
                time.sleep(0.01)

    def start(self):
        self._recording = True
        self._events = []
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._recording = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    @property
    def events(self) -> list[RecordedEvent]:
        return list(self._events)

    def assert_order(self, event_names: list[str]) -> None:
        """Assert that the given events occurred in the specified order."""
        recorded_names = [e.name for e in self._events]
        indices = []
        for name in event_names:
            try:
                # Find the first occurrence after the last found index
                start = indices[-1] + 1 if indices else 0
                idx = recorded_names.index(name, start)
                indices.append(idx)
            except ValueError:
                raise AssertionError(
                    f"Event {name!r} not found in recorded events "
                    f"(after index {indices[-1] if indices else 0}). "
                    f"Recorded: {recorded_names}"
                )

    def assert_received(self, event_name: str) -> None:
        """Assert that a specific event was received."""
        names = [e.name for e in self._events]
        if event_name not in names:
            raise AssertionError(f"Event {event_name!r} not received. Got: {names}")

    def assert_not_received(self, event_name: str) -> None:
        """Assert that a specific event was NOT received."""
        names = [e.name for e in self._events]
        if event_name in names:
            raise AssertionError(
                f"Event {event_name!r} was unexpectedly received. Got: {names}"
            )


def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    poll_interval: float = 0.05,
) -> None:
    """Wait for a condition to become true."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if condition():
                return
        except Exception:
            pass
        time.sleep(poll_interval)
    raise TimeoutError(f"Condition not met within {timeout}s")


def wait_for_x_event(
    display: Display,
    event_name: str,
    window: Window | None = None,
    timeout: float = 5.0,
) -> RecordedEvent | None:
    """Wait for a specific X11 event."""
    target_type = _EVENT_TYPE_MAP.get(event_name)
    if target_type is None:
        raise ValueError(f"Unknown event type: {event_name!r}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count = display.pending_events()
        if count > 0:
            event = display.next_event()
            if event.type == target_type:
                # If window filter, check it
                if window is not None:
                    ev_wid = None
                    if hasattr(event, "window") and hasattr(event.window, "id"):
                        ev_wid = event.window.id
                    if ev_wid != window.id and ev_wid != window.frame.id:
                        continue
                return RecordedEvent(
                    name=event_name,
                    event_type=event.type,
                    window_id=getattr(getattr(event, "window", None), "id", None),
                    timestamp=time.monotonic(),
                )
        else:
            time.sleep(0.01)

    raise TimeoutError(f"Event {event_name!r} not received within {timeout}s")
