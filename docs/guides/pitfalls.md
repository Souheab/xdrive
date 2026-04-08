# X11 Pitfalls & Gotchas

Working with X11 programmatically comes with a few surprises.  This page
collects the most common issues.

## `DISPLAY` environment variable

Every X11 client reads the `DISPLAY` variable to know which server to
connect to.  If your tests fail with connection errors, check that
`DISPLAY` is set and points to a running server:

```bash
echo $DISPLAY   # e.g. ":99"
```

When using `VirtualDisplay`, xdrive sets the display name internally — but
if you launch child processes yourself, you must pass the correct
`DISPLAY` in their environment.

## Timing and race conditions

X11 is asynchronous.  A `map_window()` call returns immediately; the
server and window manager process the request later.  Always **wait for
the expected state** rather than inserting fixed `time.sleep()` calls:

```python
# Bad
win = xd.new_window(title="test")
time.sleep(1)
assert win.is_mapped

# Good
win = xd.new_window(title="test")
xd.wait_for(lambda: win.is_mapped, timeout=3.0)
expect(win).to_be_mapped()
```

`XDrive.wait_for()` polls a condition with a configurable timeout and is
the recommended approach.

## Focus stealing and input

Many window managers enforce focus-stealing prevention.  Synthesised
`XTest` key/mouse events go to the **currently focused** window, which may
not be the window you just created.  Explicitly focus the target first:

```python
win.focus()
xd.keyboard.type("hello")
```

## Root window events

xdrive configures event masks on the root window to receive
`SubstructureNotify` and `PropertyChange`.  If another client (e.g. a
second XDrive instance) changes these masks, events may be lost.  Stick to
**one XDrive connection per display**.

## Window geometry and reparenting

Window managers typically *reparent* client windows into a frame window
that adds decorations (title bar, borders).  This means:

* `Window.geometry` returns the client area, translated to root
  coordinates.
* `Window.frame` walks up the tree to find the outermost frame.
* Geometry assertions should account for decoration sizes, which vary
  between window managers.

## XTest extension

`Keyboard` and `Mouse` rely on the **XTest** extension to inject synthetic
events.  If XTest is not available (unusual, but possible in stripped
containers), input synthesis will fail.  Ensure your Xvfb build includes
XTest support, the default packages do.

## Screenshot colour format

X11 returns pixel data in `BGRX` format. xdrive converts this to RGB via
Pillow automatically, but if you work with raw image data, keep the byte
order in mind.

## Multi-monitor (Xinerama / RandR)

`VirtualDisplay` creates a single-screen Xvfb by default.  For
multi-monitor testing, pass multiple screens:

```python
VirtualDisplay(screens=[(1920, 1080), (1280, 720)])
```

Screen numbering uses the standard X11 convention (`:99.0`, `:99.1`).
