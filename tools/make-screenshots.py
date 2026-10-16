#!/usr/bin/env python3
"""Capture the app's screens from a BUSY Bar and render them for the docs.

The bar's display pixels are round lamps with gaps, not square pixels; squares
are also what `/api/screen` hands back, with red and blue exchanged relative to
the panel. This tool drives the app over the bar's own input API, captures the
states, undoes the colour swap, and renders every pixel as a round lamp — the
way the panel actually looks.

    python3 tools/make-screenshots.py --addr <host> [--out docs]

The app must be installed and running, sitting on its ready screen. The tool
sets the duration to 25 s through the encoder for the long states and restores
5 s at the end. Output: the five state images, a state stack, and a countdown
GIF (one full 5 s run, warning and finish included).
"""

import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

STATE_NAMES = ["ready", "running", "paused", "warning", "finished"]

# Lamp rendering: each framebuffer pixel becomes a circle with a gap, drawn at
# a supersampled size and scaled down, which is what makes the edges smooth.
SUPERSAMPLE = 4
LAMP_GAP = 0.22


def render_lamps(img, scale):
    s = scale * SUPERSAMPLE
    diameter = s - max(2, int(round(s * LAMP_GAP)))
    big = Image.new("RGB", (img.width * s, img.height * s), (0, 0, 0))
    draw = ImageDraw.Draw(big)
    px = img.load()
    offset = (s - diameter) // 2
    for y in range(img.height):
        for x in range(img.width):
            color = px[x, y]
            if max(color) == 0:
                continue
            x0 = x * s + offset
            y0 = y * s + offset
            draw.ellipse((x0, y0, x0 + diameter, y0 + diameter), fill=color)
    return big.resize((img.width * scale, img.height * scale), Image.LANCZOS)


class Bar:
    def __init__(self, addr):
        self.base = f"http://{addr}"

    def press(self, key, wait=0.0):
        urllib.request.urlopen(f"{self.base}/api/input?key={key}", data=b"", timeout=5).read()
        if wait:
            time.sleep(wait)

    def screen(self):
        """The front display as logical pixels, colour order corrected.

        The endpoint answers base64 of the raw framebuffer bytes (its
        image/bmp content type notwithstanding), three bytes per pixel in BGR
        order, and the capture has red and blue exchanged relative to the
        panel.
        """
        raw = base64.b64decode(
            urllib.request.urlopen(f"{self.base}/api/screen?display=0", timeout=5).read()
        )
        img = Image.frombytes("RGB", (72, 16), raw)
        r, g, b = img.split()
        return Image.merge("RGB", (b, g, r))


def red_ink(img):
    px = img.load()
    return sum(1 for y in range(16) for x in range(20, 72)
               if px[x, y][0] > 150 and px[x, y][1] < 80)


def white_ink(img):
    px = img.load()
    return sum(1 for y in range(16) for x in range(20, 72) if min(px[x, y]) > 120)


def ours(img):
    """True when the screen is this app's.

    The bar pops its own screens over running apps (meeting reminders, for
    one), and those use saturated blues and greens; this app only ever draws
    white, warm greys, ambers and red. The app's own drawing also always has
    the hourglass at the left edge, which the launcher's screens (its
    Loading screen included) do not.
    """
    px = img.load()
    icon_ink = 0
    for y in range(16):
        for x in range(72):
            r, g, b = px[x, y]
            if b > 120 and b > r + 40 and b > g + 40:
                return False
            if g > 120 and g > r + 40 and g > b + 40:
                return False
            if x <= 14 and (r * 299 + g * 587 + b * 114) // 1000 > 20:
                icon_ink += 1
    return icon_ink >= 10


def our_screen(bar, timeout=15.0):
    """Waits for this app to be the visible screen, then returns its frame."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        img = bar.screen()
        if ours(img):
            return img
        time.sleep(0.4)
    raise RuntimeError("the bar is showing something else; is the timer app running?")


def best_of(bar, n, score, gap=0.09):
    shots = []
    for _ in range(n):
        img = bar.screen()
        if ours(img):
            shots.append(img)
        time.sleep(gap)
    if not shots:
        raise RuntimeError("no frames of the timer app in the window")
    return max(shots, key=score)


def set_duration(bar, seconds, step=5):
    """Sets the duration with spaced encoder clicks (no fast-turn bursts).

    Reads the stored value first: the app keeps its duration across runs, so a
    fixed number of clicks would land anywhere depending on where a previous
    session left it.
    """
    doc = json.loads(
        urllib.request.urlopen(
            f"{bar.base}/api/apps/settings?app_id=net.ralphm.timer", timeout=5
        ).read()
    )
    current = int(doc.get("values", {}).get("duration", 5))
    clicks = abs(seconds - current) // step
    key = "up" if seconds > current else "down"
    for _ in range(clicks):
        bar.press(key, 0.35)
    time.sleep(0.4)


def capture_states(bar, scale):
    """Captures the five states so they read as one countdown: the ready
    screen shows the run's full duration, then the run is caught mid-way, at
    the pause, at the red warning, and at the finish."""
    images = {}

    set_duration(bar, 25)
    images["ready"] = our_screen(bar)      # the start value of the run below

    bar.press("start")
    time.sleep(5.0)                        # 00:20 of the 25 s run
    images["running"] = best_of(bar, 4, white_ink)

    time.sleep(6.0)                        # ~00:14, then pause: ~00:13
    bar.press("start", 0.7)
    images["paused"] = our_screen(bar)

    bar.press("start")                     # resume into the red warning
    deadline = time.time() + 30
    while time.time() < deadline:
        img = bar.screen()
        if ours(img) and red_ink(img) > 8:
            break
        time.sleep(0.25)
    images["warning"] = best_of(bar, 8, red_ink)

    time.sleep(4.6)                        # past zero into the finish flash
    images["finished"] = best_of(bar, 9, red_ink, gap=0.12)

    bar.press("back", 0.8)
    set_duration(bar, 5)

    rendered = {name: render_lamps(images[name], scale) for name in STATE_NAMES}

    gap = 2 * scale
    width = rendered["ready"].width
    height = sum(i.height for i in rendered.values()) + gap * (len(STATE_NAMES) - 1)
    stack = Image.new("RGB", (width, height), (16, 16, 16))
    y = 0
    for name in STATE_NAMES:
        stack.paste(rendered[name], (0, y))
        y += rendered[name].height + gap
    rendered["states"] = stack
    return rendered


def capture_countdown(bar, scale):
    """One full 10 s run from the ready screen: the white countdown, the red
    last seconds with their flashing, and the finish — a hero loop.

    Captures as fast as the screen endpoint answers, then subsamples to a
    steady 20 fps for playback, so the GIF runs in real time whatever the
    capture rate happened to be.
    """
    set_duration(bar, 10)
    frames = []
    times = []
    skipped = 0
    bar.press("start")
    t0 = time.time()
    while time.time() - t0 < 13.4:
        img = bar.screen()
        if ours(img):
            frames.append(img)
            times.append(time.time())
        else:
            skipped += 1
    set_duration(bar, 5)
    if skipped:
        raise RuntimeError(f"{skipped} captured frames showed another app; re-run")
    if len(frames) < 60:
        raise RuntimeError(f"only {len(frames)} frames captured; re-run")

    dt = (times[-1] - times[0]) / (len(frames) - 1)
    step = max(1, round(0.05 / dt))
    picked = frames[::step]
    duration_ms = max(20, int(round(dt * step * 1000)))
    gif = [render_lamps(f, scale) for f in picked]
    return gif, duration_ms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addr", required=True, help="the bar's address")
    parser.add_argument("--out", default="docs", type=Path, help="output directory")
    parser.add_argument("--scale", default=10, type=int, help="pixels per lamp")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    bar = Bar(args.addr)

    rendered = capture_states(bar, args.scale)
    for name, img in rendered.items():
        img.save(args.out / f"{name}.png")
        print(f"wrote {args.out / (name + '.png')}")

    gif, duration_ms = capture_countdown(bar, args.scale)
    gif[0].save(args.out / "countdown.gif", save_all=True, append_images=gif[1:],
                duration=duration_ms, loop=0, optimize=True)
    print(f"wrote {args.out / 'countdown.gif'} ({len(gif)} frames at {duration_ms} ms)")


if __name__ == "__main__":
    main()
