# Quick Start

## Installation

```bash
pip install -e .
```

xdrive requires an X11 environment (real or virtual). For headless CI, see
the [Headless Display Setup](headless.md) guide.

## Your First Test

```python
from xdrive import XDrive, VirtualDisplay, expect

# Start a virtual X display and connect
with VirtualDisplay(width=1280, height=720) as vd:
    with XDrive(display=vd, wm="./my_wm") as xd:
        # Create a test window
        win = xd.new_window(title="hello", size=(400, 300))

        # Assert the window is mapped and has the right title
        expect(win).to_be_mapped()
        expect(win).to_have_title("hello")

        # Interact with mouse and keyboard
        xd.mouse.click(win)
        xd.keyboard.type("Hello, world!")

        # Take a screenshot
        xd.screenshot("output/screenshot.png")
```

## Using the Pytest Fixtures

xdrive ships as a pytest plugin.  The built-in fixtures handle display and
connection lifecycle for you:

```python
def test_window_title(xd):
    """``xd`` is a per-test XDrive instance on a session-scoped Xvfb."""
    win = xd.new_window(title="my window")
    expect(win).to_have_title("my window")
```

Override the `virtual_display` or `xd` fixtures in your own `conftest.py`
to customise resolution, colour depth, or window manager command.

## Key Concepts

| Object            | Purpose                                         |
| ----------------- | ----------------------------------------------- |
| `VirtualDisplay`  | Manage an Xvfb instance                         |
| `XDrive`          | Main controller — windows, input, screenshots   |
| `Window`          | Query and manipulate a single X11 window        |
| `Screen`          | Query display-wide state (window list, focus)    |
| `Keyboard`        | Synthesise key events via XTest                  |
| `Mouse`           | Synthesise pointer events via XTest              |
| `expect()`        | Playwright-style fluent assertions               |
