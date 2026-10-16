#!/usr/bin/env python3
"""Draw the timer's hourglass frames.

The icon beside the time is a real hourglass: the sand sits in one bulb or the
other, and during the countdown it drains from the top into the bottom.
`src/images/hourglass-NN.png` holds one frame per step of that drain (NN
counting up as the sand falls) and `hourglass-flip-*.png` the spin at the
start. Pausing lays the glass on its side — a real hourglass cannot pause
otherwise: `hourglass-tip-K-NN.png` are the frames of that tip (K counting up
as it goes over) and `hourglass-side-NN.png` the resting pose, all per drain
step. The pouring animation that gives the glass life is a separate overlay,
built by `make-animation.py`.

Drawn at 16x16 with hard edges, because the display's pixels are round lamps:
a half-lit lamp reads as a dim lamp, not as a soft edge. Depth comes from
varying brightness across neighbouring lamps — a lit top-left rim, a dark
glass, dithered sand — never from smooth gradients.

    python3 tools/make-icon.py
"""

import math
from pathlib import Path

from PIL import Image

SIZE = 16
CX = 8.5            # a little right of centre in the cell
TOP, BOTTOM = 1, 14
WAIST = 1.2          # half-width at the neck: rim plus a one-lamp channel
WIDE = 4.5           # half-width at the caps
CY = (TOP + BOTTOM) / 2
HALF = CY - TOP

RIM_LIT = (255, 255, 255)
GLASS = (24, 19, 12)
SAND_TOP = (255, 196, 96)
SAND_BOT = (206, 62, 0)
MENISCUS = (255, 236, 180)
HIGHLIGHT = (255, 242, 220)

DRAIN_STEPS = 21
# The tip while pausing (and back while resuming): intermediate angles as a
# fraction of the quarter turn, then the resting pose itself.
TIP_STEPS = [0.28, 0.56, 0.83]
# The turn at the start: the glass spins over, in this many frames.
TURN_STEPS = 8

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


def scale(color, factor):
    return tuple(max(0, min(255, int(round(c * factor)))) for c in color)


def half_width(y):
    t = min(1.0, abs(y - CY) / HALF)
    return WAIST + (WIDE - WAIST) * (t ** 0.6)


def draw(top_fraction):
    """One upright frame: `top_fraction` of the sand in the upper bulb.

    Hard rows: everything is drawn on the lamp grid.
    """
    img = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    px = img.load()

    top_y = round(CY - HALF)
    bottom_y = round(CY + HALF)
    span = max(1.0, bottom_y - top_y)

    top_rows = CY - top_y
    sand_surface = CY - top_fraction * top_rows
    heap_h = (1.0 - top_fraction) * (bottom_y - CY)

    for y in range(top_y, bottom_y + 1):
        left, right = round(CX - half_width(y)), round(CX + half_width(y))
        across_span = max(1, right - left)
        down = (y - top_y) / span

        for x in range(left, right + 1):
            across = (x - left) / across_span
            edge = x == left or x == right or y == top_y or y == bottom_y
            shade = 1.0 - 0.55 * (0.5 * down + 0.5 * across)

            if edge:
                px[x, y] = scale(RIM_LIT, shade)
                continue

            # Interior: sand where the column has reached, glass elsewhere.
            if y <= CY:
                in_sand = y >= round(sand_surface)
                heap = 0.0
            else:
                in_sand = heap_h > 0 and y >= bottom_y - heap_h
                heap = heap_h

            if not in_sand:
                px[x, y] = GLASS
                # A dim reflection in the empty glass, top-left, so the bulb
                # reads as a vessel with volume rather than a hole.
                if x == left + 1 and y <= CY:
                    px[x, y] = lerp(GLASS, RIM_LIT, 0.18)
                continue

            # The settled heap is a mound centred under the neck; the sand
            # above the neck is a flat body whose surface drops as it drains.
            if y > CY and heap > 0:
                span_w = WIDE * 0.92
                height_here = heap * max(0.0, 1.0 - abs(x - CX) / span_w)
                if y == round(bottom_y - height_here):
                    base = lerp(SAND_TOP, SAND_BOT, down ** 0.8)
                    px[x, y] = lerp(base, MENISCUS, 0.55)
                    continue

            base = lerp(SAND_TOP, SAND_BOT, down ** 0.8)
            value = tuple(int(round(c * (1.0 - 0.18 * across))) for c in base)
            # Granular texture: a scatter of dimmer grains, so the sand reads
            # as poured rather than flooded — subtle, or it turns muddy.
            if (2 * x + y) % 3 == 0 and y != round(sand_surface):
                value = scale(value, 0.92)
            # The surface line catches the light.
            if y == round(sand_surface) and y <= CY:
                value = lerp(base, MENISCUS, 0.7)
            # A specular streak inside the left of the sand, where the glass
            # catches the light.
            if x == left + 1 and y != round(sand_surface) and not (y > CY):
                value = HIGHLIGHT
            px[x, y] = value

    return img


def resting_cut(rows, fraction):
    """The column a bulb's sand settles to when the glass lies down.

    On its side, the glass's gravity runs across it, so the sand in each bulb
    rests against one wall as a slab: all columns at or beyond `cut` carry
    sand. The cut is placed so the slab holds `fraction` of the bulb's area.
    """
    counts = {}
    for y in rows:
        left, right = round(CX - half_width(y)), round(CX + half_width(y))
        for x in range(left, right + 1):
            counts[x] = counts.get(x, 0) + 1

    target = fraction * sum(counts.values())
    acc = 0
    for x in sorted(counts, reverse=True):
        if acc + counts[x] >= target:
            return x
        acc += counts[x]
    return min(counts)


def turned_interior(x, y, top_fraction, tipped):
    """The glass interior at a body cell, for a glass `tipped` towards its side.

    The sand's boundary sweeps from the upright surface to the resting slab as
    the angle grows — the same thing a real glass does when laid down. `tipped`
    is capped at the quarter turn: past it the sand is along for the ride.
    """
    left = round(CX - half_width(y))
    across = (x - left) / max(1, round(CX + half_width(y)) - left)
    down = (y - TOP) / (BOTTOM - TOP)

    if y <= CY:
        surface = round(CY - top_fraction * (CY - TOP))
        cut = resting_cut(range(TOP, int(CY) + 1), top_fraction)
    else:
        surface = BOTTOM - (1.0 - top_fraction) * (BOTTOM - CY)
        cut = resting_cut(range(int(CY) + 1, BOTTOM + 1), 1.0 - top_fraction)
    depth = (1.0 - tipped) * (y - surface) + tipped * (x - cut)

    if depth < 0:
        return lerp(GLASS, RIM_LIT, 0.18) if (x == left + 1 and y <= CY) else GLASS

    # The sand's colour deepens with its distance from the free surface, which
    # the blend swings from vertical (upright) to across (on its side).
    side = min(1.0, max(0.0, (x - cut) / max(1.0, (CX + WIDE) - cut)) * 1.3)
    base = lerp(SAND_TOP, SAND_BOT, (1.0 - tipped) * (down ** 0.8) + tipped * side)
    value = tuple(int(round(c * (1.0 - 0.18 * across))) for c in base)
    if (2 * x + y) % 3 == 0 and depth > 1:
        value = scale(value, 0.92)
    if abs(depth) < 0.6:
        value = lerp(base, MENISCUS, 0.7)
    if x == left + 1 and y <= CY and depth > 1:
        value = HIGHLIGHT
    return value


def inside_glass(bx, by):
    """Whether a (float) body-coordinate point is inside the glass."""
    return TOP <= by <= BOTTOM and abs(bx - CX) <= half_width(by)


# Sub-cell sample points, for deciding a lamp from its coverage.
SUBSAMPLES = tuple((sx, sy) for sy in (1, 3, 5) for sx in (1, 3, 5))


def draw_turned(top_fraction, angle_deg):
    """The glass turned clockwise by `angle_deg`, rendered on the lamp grid.

    Each lamp is decided by covering it with sub-cell samples of the rotated
    body: a lamp is glass when most of it is glass, which keeps the silhouette
    a clean lamp shape at any angle (at right angles the mapping is exact).
    The outline and its lighting are then computed in screen coordinates — a
    complete one-lamp rim, lit from the top left as in the upright frames, so
    a turned glass keeps the same lit-object look rather than rotating its
    lighting.
    """
    img = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    px = img.load()
    angle = math.radians(angle_deg)
    tipped = min(1.0, abs(angle_deg) / 90.0)
    c = (SIZE - 1) / 2
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def body_at(dx, dy):
        xx, yy = dx - c, dy - c
        return (xx * cos_a + yy * sin_a + c, -xx * sin_a + yy * cos_a + c)

    cells = {}
    if abs(angle_deg - 90.0) < 1e-6:
        # At the right angle the turn is exact: transpose the lamp grid, so
        # the resting pose is a true rotated copy of the upright glass — same
        # lamps, same sand, only the outline's lighting is redone below.
        for by in range(TOP, BOTTOM + 1):
            for bx in range(round(CX - half_width(by)), round(CX + half_width(by)) + 1):
                cells[(SIZE - 1 - by, bx)] = (bx, by)
    else:
        for dy in range(SIZE):
            for dx in range(SIZE):
                inside = 0
                for sx, sy in SUBSAMPLES:
                    bx, by = body_at(dx - 0.5 + sx / 6, dy - 0.5 + sy / 6)
                    if inside_glass(bx, by):
                        inside += 1
                if inside * 2 < len(SUBSAMPLES):
                    continue
                bx, by = body_at(dx, dy)
                if inside_glass(bx, by):
                    cells[(dx, dy)] = (round(bx), round(by))

    xs = [p[0] for p in cells]
    ys = [p[1] for p in cells]
    span_x = max(1, max(xs) - min(xs))
    span_y = max(1, max(ys) - min(ys))

    for (dx, dy), (bx, by) in cells.items():
        if any(n not in cells for n in ((dx + 1, dy), (dx - 1, dy), (dx, dy + 1), (dx, dy - 1))):
            down = (dy - min(ys)) / span_y
            across = (dx - min(xs)) / span_x
            px[dx, dy] = scale(RIM_LIT, 1.0 - 0.55 * (0.5 * down + 0.5 * across))
            continue
        px[dx, dy] = turned_interior(bx, by, top_fraction, tipped)

    return img


def draw_badge(rows, size, frame, sand_top, sand_bottom, glass):
    """One of the app's own icons: frame, empty glass above, sand below."""
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

    # Pausing lays the glass down: one frame per tip step per drain level, and
    # the resting pose itself. The tip is the same art as the drain, only
    # turned, so resuming replays these frames backwards.
    for step in range(DRAIN_STEPS):
        top_fraction = 1.0 - step / (DRAIN_STEPS - 1)
        for i, tipped in enumerate(TIP_STEPS):
            draw_turned(top_fraction, 90.0 * tipped).save(OUT / f"hourglass-tip-{i}-{step:02d}.png")
        draw_turned(top_fraction, 90.0).save(OUT / f"hourglass-side-{step:02d}.png")

    # The turn at the start: the spent glass spins over half a turn, so the
    # pile travels to the top of the screen and the first drain frame picks up
    # seamlessly — the same rotation as the pause tip, carried on.
    for i in range(TURN_STEPS):
        angle = 180.0 * (i + 1) / (TURN_STEPS + 1)
        draw_turned(0.0, angle).save(OUT / f"hourglass-flip-{i}.png")

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

    print(f"wrote {DRAIN_STEPS} drain frames, {len(TIP_STEPS)}x{DRAIN_STEPS} tip frames, "
          f"{DRAIN_STEPS} side frames, {TURN_STEPS} flip frames and the two menu icons")


if __name__ == "__main__":
    main()
