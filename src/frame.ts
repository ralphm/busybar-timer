// What the screen shows. Pure: no device access, so it can be reasoned about
// (and checked by hand) without hardware.

import type { DisplayElement } from "@shared/device";
import { formatTime, WARN_SECONDS, type TimerState } from "./timer.ts";

/** The front display. */
const SCREEN_WIDTH = 72;
const SCREEN_HEIGHT = 16;

/**
 * A 16×16 icon from the device's own sticker set, pinned hard left. It is a
 * stock image, so it costs no asset of ours, and it never flashes — only the
 * time does. Its ink ends at column 12.
 */
const ICON = "shared/images/dt_study.image";
const ICON_INK_RIGHT = 13;

/**
 * Metrics of the device's `bold` font, read from its own glyph tables. Every
 * digit advances the same 7 px, so a countdown never shifts as its digits
 * change; the ink is 7 px tall and starts 2 px below the line top.
 */
const ADVANCE: Record<string, number> = {
  "0": 7, "1": 7, "2": 7, "3": 7, "4": 7, "5": 7, "6": 7, "7": 7, "8": 7, "9": 7,
  ":": 2,
  D: 7, O: 7, N: 8, E: 6, " ": 5,
};
const FONT = "bold";
const INK_HEIGHT = 7;
const CAP_TOP = 2;

const TIME_Y = Math.floor((SCREEN_HEIGHT - INK_HEIGHT) / 2) - CAP_TOP;

const WHITE = "#FFFFFFFF";
/** Paused: the time stays readable but visibly inert. */
const DIM = "#FFFFFF80";
/** The colon on its dim half, as the device's own clock dims it. */
const BLINKED = "#FFFFFF66";
const RED = "#FF0000FF";
/** The dark half of the flash: drawn, but invisible. */
const OFF = "#00000000";

/** One frame's worth of state. */
export interface View {
  state: TimerState;
  /** Whole seconds the app is showing. */
  seconds: number;
  /** The lit half of the flash cycle. Only meaningful while warning or finished. */
  flashOn: boolean;
  /** Which half of the colon's blink is current. Only meaningful while running. */
  colonLit: boolean;
}

/** A finished countdown or the last seconds of one flashes; nothing else does. */
export function isFlashing(view: View): boolean {
  return view.state === "finished" || (view.state === "running" && view.seconds <= WARN_SECONDS);
}

/** The colour the status LED should blink, or undefined to leave the LED alone. */
export function ledColor(view: View): string | undefined {
  return isFlashing(view) ? RED : undefined;
}

/** Where the text starts: centred in the space the icon leaves. */
function textX(text: string): number {
  let width = 0;
  for (const char of text) width += ADVANCE[char] ?? ADVANCE["0"]!;

  // Rounded, not floored: the last glyph's ink stops short of its advance, so
  // the visible gap on the right would otherwise look wider than the left one.
  return Math.round((ICON_INK_RIGHT + SCREEN_WIDTH - width) / 2);
}

/**
 * The frame: the icon and the time. Element ids stay the same in every state —
 * the device keeps elements it is not told about, so changing ids between
 * states would leave the old ones on screen.
 */
export function elements(view: View): DisplayElement[] {
  const flashing = isFlashing(view);
  const lit = !flashing || view.flashOn;
  const color = flashing ? (lit ? RED : OFF) : view.state === "paused" ? DIM : WHITE;
  const colonColor =
    flashing || view.state !== "running" ? color : view.colonLit ? WHITE : BLINKED;

  // "DONE" keeps the same element ids as the time, so nothing lingers.
  const text = view.state === "finished" ? "DONE" : formatTime(view.seconds);

  const out: DisplayElement[] = [
    {
      type: "image",
      id: "icon",
      stock_path: ICON,
      x: 0,
      y: 0,
      align: "top_left",
      display: "front",
    },
  ];

  let x = textX(text);
  for (let i = 0; i < text.length; i++) {
    const char = text[i]!;
    out.push({
      type: "text",
      id: `c${i}`,
      text: char,
      font: FONT,
      color: char === ":" ? colonColor : color,
      x,
      y: TIME_Y,
      align: "top_left",
      display: "front",
    });
    x += ADVANCE[char] ?? ADVANCE["0"]!;
  }

  return out;
}
