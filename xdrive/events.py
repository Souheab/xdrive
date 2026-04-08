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
    """A recorded X11 event captured by :class:`EventRecorder`.

    Attributes:
        name: Human-readable event name (e.g. ``'MapNotify'``).
        event_type: Integer X11 event type constant.
        window_id: X11 window ID the event was delivered to, or ``None``.
        timestamp: Monotonic timestamp (``time.monotonic()``) when the
            event was captured.
    """

    name: str
    event_type: int
    window_id: int | None = None
    timestamp: float = 0.0


class EventRecorder:
    """Record X11 events in a background thread for later assertion.

    Used via :meth:`XDrive.record_events` as a context manager.  While
    recording, a daemon thread polls ``display.pending_events()`` and
    stores each event as a :class:`RecordedEvent`.

    Args:
        display: An open ``Xlib.display.Display`` connection.

    Example:
        >>> with xd.record_events() as rec:
        ...     win = xd.new_window()
        >>> rec.assert_received("MapNotify")
    """

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
        """Begin recording events in a background thread."""
        self._recording = True
        self._events = []
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the recording thread and wait for it to exit."""
        self._recording = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    @property
    def events(self) -> list[RecordedEvent]:
        """Return a snapshot of all recorded events so far."""
        return list(self._events)

    def assert_order(self, event_names: list[str]) -> None:
        """Assert that events occurred in the given order.

        Each event name must appear after the previous one in the
        recording.  Extra events between them are allowed.

        Args:
            event_names: Ordered list of X11 event names
                (e.g. ``['MapNotify', 'ConfigureNotify']``).

        Raises:
            AssertionError: If the ordering is violated or an event
                is missing.
        """
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
        """Assert that a specific X11 event was recorded.

        Args:
            event_name: Event name such as ``'MapNotify'``.

        Raises:
            AssertionError: If the event was not found.
        """
        names = [e.name for e in self._events]
        if event_name not in names:
            raise AssertionError(f"Event {event_name!r} not received. Got: {names}")

    def assert_not_received(self, event_name: str) -> None:
        """Assert that a specific X11 event was **not** recorded.

        Args:
            event_name: Event name such as ``'DestroyNotify'``.

        Raises:
            AssertionError: If the event was found.
        """
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
    """Poll a callable until it returns ``True`` or the timeout expires.

    Args:
        condition: A zero-argument callable that returns a boolean.
        timeout: Maximum time to wait in seconds.
        poll_interval: Seconds between successive polls.

    Raises:
        TimeoutError: If *condition* does not return ``True`` within
            *timeout* seconds.

    Example:
        >>> wait_for_condition(lambda: win.is_mapped, timeout=3.0)
    """
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
    """Block until a specific X11 event is received.

    Events are consumed from the display connection until one matching
    *event_name* (and optionally *window*) is found.

    Args:
        display: An open ``Xlib.display.Display``.
        event_name: Name of the event to wait for (e.g.
            ``'MapNotify'``).
        window: If given, only events targeting this window or its
            frame are accepted.
        timeout: Maximum wait time in seconds.

    Returns:
        The matching :class:`RecordedEvent`.

    Raises:
        ValueError: If *event_name* is not a known X11 event type.
        TimeoutError: If the event is not received in time.
    """
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
