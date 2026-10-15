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
CX = 8.5            # a little right of centre in the cell
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
FLIP_TUMBLE = [1.0, 0.62, 0.22, 0.62, 1.0]

SRC = Path(__file__).resolve().parent.parent / "src"
OUT = SRC / "images"

# The apps-menu icons: the shape below, 5x7 in an 8x8 canvas, and the same idea
# as a plain hourglass for the monochrome back display.
MENU_SHAPE = """*****
*000*
 *0*
 *0*
 *0*
*000*
*****""".split("\n")

BACK_SHAPE = """###########
#000000000#
.#0000000#.
..#00000#..
...#000#...
....#0#....
...#000#...
..#00000#..
.#0000000#.
#000000000#
###########""".split("\n")


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


def tumbled(img, height_fraction):
    """The same frame mid-turn: an hourglass is turned end over end, so the
    glass shortens towards its middle — a turn about the horizontal axis."""
    height = max(1, int(round(SIZE * height_fraction)))
    short = img.resize((SIZE, height), Image.NEAREST)
    out = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    out.paste(short, (0, (SIZE - height) // 2))
    return out


def draw_badge(rows, size, frame, sand_top, sand_bottom, glass):
    """One of the app's own icons: fram, empty glass above, sand below."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    height = len(rows)
    offset = (size - height) // 2
    middle = height / 2

    for y, row in enumerate(rows):
        for i, c in enumerate(row):
            if c in " .":
                continue
            x = offset + i
            if c == "*" or c == "#":
                px[x, y + offset] = frame
            elif y + 0.5 >= middle:
                # the lower half holds the sand, deeper towards the bottom
                px[x, y + offset] = sand_top if y < middle else sand_bottom
            else:
                px[x, y + offset] = glass
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (SRC / "appmeta").mkdir(parents=True, exist_ok=True)

    for step in range(DRAIN_STEPS):
        # step 0 is a full upper bulb — the moment the hourglass has been turned
        top_fraction = 1.0 - step / (DRAIN_STEPS - 1)
        draw(top_fraction).save(OUT / f"hourglass-{step:02d}.png")

    # The turn: the glass shortening end over end, then opening out again with
    # the sand at the top. It begins and ends at full height, so it joins the
    # spent glass before it and the full one after.
    for i, squash in enumerate(FLIP_TUMBLE):
        spent = draw(0.0) if i < len(FLIP_TUMBLE) // 2 else draw(1.0)
        tumbled(spent, squash).save(OUT / f"hourglass-flip-{i}.png")

    # The icons the apps menu shows, in the same colours as the glass beside
    # the time: white frame, orange sand in the lower half, dim empty glass.
    draw_badge(
        MENU_SHAPE, 8,
        (255, 255, 255, 255), (255, 176, 76, 255), (238, 126, 28, 255), GLASS + (255,),
    ).save(SRC / "appmeta" / "icon_front_8x8.png")

    # The back display is monochrome, so the same design in greys.
    draw_badge(
        BACK_SHAPE, 11,
        (255, 255, 255, 255), (232, 232, 232, 255), (170, 170, 170, 255), (26, 26, 26, 255),
    ).save(SRC / "appmeta" / "icon_back_11x11.png")

    print(f"wrote {DRAIN_STEPS} drain frames, {len(FLIP_TUMBLE)} flip frames and the two menu icons")


if __name__ == "__main__":
    main()
