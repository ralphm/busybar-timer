#!/usr/bin/env python3
"""Draw the timer's hourglass frames.

The icon beside the time is a real hourglass, not a solid cut-out: the sand
sits in one bulb or the other, and during the countdown it drains from the top
into the bottom. `src/images/hourglass-NN.png` holds one frame per step of that
drain (NN counting up as the sand falls), and `hourglass-flip-*.png` the short
turn at the start.

Drawn at 16x16 with hard edges, because the display's pixels are round lamps:
a half-lit lamp reads as a dim lamp, not as a soft edge. Depth comes from
varying brightness across neighbouring lamps.

    python3 tools/make-icon.py
"""

from pathlib import Path

from PIL import Image

SIZE = 16
CX = 7.5
TOP, BOTTOM = 1, 14
WAIST = 0.9          # half-width at the neck
WIDE = 4.5           # half-width at the caps
CY = (TOP + BOTTOM) / 2
HALF = (TOP + BOTTOM) / 2 - TOP

TOP_COL = (255, 196, 96)
BOTTOM_COL = (206, 62, 0)
RIM_TOP = (255, 255, 255)
GLASS = (26, 20, 12)
HIGHLIGHT = (255, 242, 220)

DRAIN_STEPS = 21
FLIP_SQUASH = [1.0, 0.55, 0.18, 0.55, 1.0]

OUT = Path(__file__).resolve().parent.parent / "src" / "images"


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def half_width(y):
    t = min(1.0, abs(y - CY) / HALF)
    return WAIST + (WIDE - WAIST) * (t ** 0.6)


def draw(top_fraction):
    """One frame: `top_fraction` of the sand in the upper bulb, the rest below."""
    img = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    px = img.load()

    top_rows = CY - TOP
    bottom_rows = BOTTOM - CY
    sand_top_from = CY - round(top_fraction * top_rows)
    sand_bottom_from = BOTTOM - round((1 - top_fraction) * bottom_rows)

    for y in range(TOP, BOTTOM + 1):
        left, right = round(CX - half_width(y)), round(CX + half_width(y))
        span = max(1, right - left)
        down = (y - TOP) / (BOTTOM - TOP)

        for x in range(left, right + 1):
            across = (x - left) / span

            if x == left or x == right or y == TOP or y == BOTTOM:
                shade = 1.0 - 0.42 * (0.5 * down + 0.5 * across)
                px[x, y] = tuple(int(round(c * shade)) for c in RIM_TOP)
                continue

            in_sand = (
                sand_top_from <= y <= CY if y <= CY else y >= sand_bottom_from
            )
            if not in_sand:
                px[x, y] = GLASS
                continue

            base = lerp(TOP_COL, BOTTOM_COL, down ** 0.8)
            px[x, y] = tuple(int(round(c * (1.0 - 0.34 * across))) for c in base)

            # A specular streak inside the left of the upper bulb, where there
            # is still glass to catch the light.
            if x == left + 1 and y <= CY and in_sand:
                px[x, y] = HIGHLIGHT

    return img


def squashed(img, width_fraction):
    """The same frame seen mid-turn: squeezed horizontally, then centred."""
    width = max(1, int(round(SIZE * width_fraction)))
    narrow = img.resize((width, SIZE), Image.NEAREST)
    out = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    out.paste(narrow, ((SIZE - width) // 2, 0))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    for step in range(DRAIN_STEPS):
        # step 0 is a full upper bulb — the moment the hourglass has been turned
        top_fraction = 1.0 - step / (DRAIN_STEPS - 1)
        draw(top_fraction).save(OUT / f"hourglass-{step:02d}.png")

    # The turn: the spent glass squeezing edge-on, then the full one widening
    # back out. It begins and ends at full width so it joins both states.
    for i, squash in enumerate(FLIP_SQUASH):
        spent = draw(0.0) if i < len(FLIP_SQUASH) // 2 else draw(1.0)
        squashed(spent, squash).save(OUT / f"hourglass-flip-{i}.png")

    print(f"wrote {DRAIN_STEPS} drain frames and {len(FLIP_SQUASH)} flip frames to {OUT}")


if __name__ == "__main__":
    main()
