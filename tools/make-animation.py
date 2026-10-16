#!/usr/bin/env python3
"""Draw and pack the hourglass' pouring animation.

`src/animations/hourglass-stream.anim` is the life of the drawing: grains
falling through the neck, a faint glow at the waist, and a spark where the
grains land on the heap. It is an overlay — a 16x16 frame with everything else
transparent — drawn on top of the drain frames by the app while the countdown
runs.

The frames are packed with the firmware's own converter, which is the only
supported way to author the device's animation format:

    python3 -m pip install pillow colorlog
    python3 tools/make-animation.py --firmware /path/to/busybar-firmware

The converter is used as a tool from its checkout (its `scripts/` tree is
GPL-2.0-or-later and is never vendored into this MIT repository); the packed
animation is this project's own artwork.
"""

import argparse
import json
import math
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

SIZE = 16
NECK_X = 8                  # the left lamp of the channel under the waist
FPS = 24
FRAME_COUNT = 24            # one second per loop
# The grain appears at the waist and falls through the channel. It must not
# start higher: the last sand sits at the waist row, so a grain above it would
# float in the empty bulb once the countdown is nearly done.
GRAIN_ROWS = [7, 8, 9]
# Three grains, evenly spaced through the loop; each falls down one lamp,
# alternating sides.
GRAIN_PHASES = [(0, NECK_X), (8, NECK_X + 1), (16, NECK_X)]

SAND_BRIGHT = (255, 222, 140)
SAND_TRAIL = (255, 190, 110)


def draw_frames():
    """One RGBA frame per loop step: transparent, except the falling sand."""
    images = []
    for f in range(FRAME_COUNT):
        pixels = {}

        def put(x, y, color, alpha):
            key = (x, y)
            if key not in pixels or pixels[key][1] < alpha:
                pixels[key] = (color, alpha)

        for phase, x in GRAIN_PHASES:
            step = (f - phase) % FRAME_COUNT
            if step < len(GRAIN_ROWS):
                put(x, GRAIN_ROWS[step], SAND_BRIGHT, 255)
                if step > 0:
                    put(x, GRAIN_ROWS[step - 1], SAND_TRAIL, 80)
            elif step == len(GRAIN_ROWS):
                # the grain has just landed: a spark on the heap's shoulder
                put(NECK_X, 11, SAND_BRIGHT, 150)

        # A faint glow at the waist, breathing with the loop, so the neck
        # never looks dead between grains.
        breath = int(28 + 22 * (1 + math.sin(2 * math.pi * f / FRAME_COUNT)))
        for y in (7, 8):
            for x in (NECK_X, NECK_X + 1):
                put(x, y, SAND_TRAIL, breath)

        img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        for (x, y), (color, alpha) in pixels.items():
            img.putpixel((x, y), color + (alpha,))
        images.append(img)
    return images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", required=True, type=Path,
                        help="Path to a busybar-firmware checkout (uses scripts/seq2anim.py)")
    args = parser.parse_args()

    converter = args.firmware / "scripts" / "seq2anim.py"
    if not converter.is_file():
        sys.exit(f"no {converter}; point --firmware at a busybar-firmware checkout")

    out = Path(__file__).resolve().parent.parent / "src" / "animations"
    out.mkdir(parents=True, exist_ok=True)
    images = draw_frames()

    with tempfile.TemporaryDirectory(prefix="hourglass-stream-") as tmp:
        staging = Path(tmp) / "hourglass-stream"
        staging.mkdir()
        (staging / "meta.json").write_text(
            json.dumps({"fps": FPS, "color_mode": "argb8888", "sections": []})
        )
        for i, img in enumerate(images):
            img.save(staging / f"frame_{i:05d}.png")
        archive = Path(tmp) / "hourglass-stream.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for png in sorted(staging.iterdir()):
                z.write(png, f"hourglass-stream/{png.name}")

        target = out / "hourglass-stream.anim"
        subprocess.run(
            [sys.executable, str(converter), "-o", str(target), str(archive)],
            check=True,
            cwd=args.firmware / "scripts",
        )

    print(f"wrote {target} ({FRAME_COUNT} frames at {FPS} fps, "
          f"{target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
