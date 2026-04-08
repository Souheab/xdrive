# Headless Display Setup

xdrive is designed to run without a physical monitor by using **Xvfb**
(X Virtual Framebuffer).

## Installing Xvfb

```bash
# Debian / Ubuntu
sudo apt-get install xvfb

# Fedora
sudo dnf install xorg-x11-server-Xvfb

# Arch
sudo pacman -S xorg-server-xvfb
```

## Using `VirtualDisplay`

The simplest approach is to let xdrive manage Xvfb for you:

```python
from xdrive import VirtualDisplay, XDrive

with VirtualDisplay(width=1920, height=1080, depth=24) as vd:
    with XDrive(display=vd, wm="my_wm") as xd:
        win = xd.new_window(title="test")
        # ...
```

`VirtualDisplay` automatically picks a free display number (`:99`–`:199`),
starts Xvfb with `-ac -nolisten tcp`, and tears it down on exit.

### Multi-screen setups

Pass a list of `(width, height)` tuples to create multiple X screens:

```python
VirtualDisplay(screens=[(1920, 1080), (1280, 720)])
```

## Manual Xvfb usage

If you prefer to manage Xvfb yourself:

```bash
Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp &
export DISPLAY=:99
pytest
```

Then instantiate XDrive without specifying a display — it reads `$DISPLAY`:

```python
with XDrive(wm="my_wm") as xd:
    ...
```

## CI Integration (GitHub Actions)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Xvfb
        run: sudo apt-get install -y xvfb
      - name: Run tests
        run: |
          pip install -e .
          pytest
```

The built-in pytest fixtures (`virtual_display`, `xd`) handle Xvfb
automatically — no wrapper script needed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Xvfb did not start in time` | Another Xvfb may hold the display number. Kill stale processes or increase the timeout. |
| `Could not find a free display number` | Too many existing X servers. Clean up `/tmp/.X*-lock` files. |
| `Xvfb exited with code 1` | Check that `xvfb` is installed and no other server owns that display. |
