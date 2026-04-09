# xdrive

**xdrive** is a Python framework for testing X11 window managers and desktop applications. It spins up a headless Xvfb display, lets you create and drive windows with real keyboard/mouse input, and provides a Playwright-inspired `expect()` assertion API all from a standard `pytest` session.

```python
# tests/test_my_wm.py
from xdrive import XDrive, expect

def test_button_click(xd):
    win = xd.new_window(title="My App", size=(800, 600))
    win.focus()
    xd.wait_for_layout()

    # Click the centre of the window
    geo = win.geometry
    xd.mouse.move(geo.x + geo.width // 2, geo.y + 40)
    xd.mouse.click()

    # Assert the window is still alive and mapped
    expect(win).to_be_mapped()
    expect(win).to_have_title("My App")
```

No physical monitor needed. No `time.sleep()` required.

---

## Why xdrive?

Testing an X11 window manager means controlling real windows at the protocol level: resizing, focus changes, keyboard grabs, reparenting which xdrive allows you to do in an automated matter.

- **Headless by default**: `VirtualDisplay` wraps Xvfb; pick a free display automatically
- **Simulate keyboard inputs**: Keyboard and mouse events can be simulated via XTest
- **Playwright-style assertions**:  `expect(win).to_have_geometry(width=640)` with clear failure messages
- **pytest-native**: drop-in session fixture; zero boilerplate in individual tests

---

## Install

```bash
pip install xdrive
```

**System dependency**: Xvfb must be present:

```bash
# Debian / Ubuntu
sudo apt-get install xvfb

# Fedora
sudo dnf install xorg-x11-server-Xvfb

# Arch
sudo pacman -S xorg-server-xvfb
```

---

## 30-second quickstart

### 1. Add fixtures to `tests/conftest.py`

```python
import pytest
from xdrive import VirtualDisplay, XDrive

@pytest.fixture(scope="session")
def virtual_display():
    with VirtualDisplay(width=1280, height=800) as vd:
        yield vd

@pytest.fixture
def xd(virtual_display):
    with XDrive(display=virtual_display) as xd:
        yield xd
```

### 2. Write a test

```python
from xdrive import expect

def test_window_resize(xd):
    win = xd.new_window(title="Resize Me", size=(400, 300))
    win.set_size(800, 600)
    xd.wait_for_layout()
    expect(win).to_have_geometry(width=800, height=600)

def test_keyboard_input(xd):
    win = xd.new_window(title="Editor")
    win.focus()
    xd.keyboard.type("hello world")
    xd.keyboard.press("ctrl+a")
    expect(win).to_be_mapped()
```

### 3. Run

```bash
pytest
```

No `DISPLAY` export needed, the session fixture starts and tears down Xvfb automatically.

---

## Key APIs

| What you want | How |
|---|---|
| New window | `xd.new_window(title="T", size=(w, h), position=(x, y))` |
| Mouse click | `xd.mouse.move(x, y)` then `xd.mouse.click()` |
| Type text | `xd.keyboard.type("hello")` |
| Press key combo | `xd.keyboard.press("ctrl+shift+t")` |
| Assert mapped | `expect(win).to_be_mapped()` |
| Assert title | `expect(win).to_have_title("My App")` |
| Assert geometry | `expect(win).to_have_geometry(width=640, height=480)` |
| Wait for state | `xd.wait_for(lambda: win.is_focused)` |
| Screenshot | `win.screenshot()` → `PIL.Image` |

---

## CI (GitHub Actions Example)

```yaml
- name: Install system deps
  run: sudo apt-get install -y xvfb

- name: Test
  run: pytest
```

The `virtual_display` fixture handles `Xvfb` internally, no `Xvfb &` wrapper script needed.

---

## Full documentation

[https://xdrive.readthedocs.io](https://xdrive.readthedocs.io)
