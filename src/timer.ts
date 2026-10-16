// The timer's rules, with no device access: what a duration may be, how the
// remaining time is written, and when the end is near.

/** What the app is doing. */
export type TimerState = "ready" | "running" | "paused" | "finished";

/** Duration bounds and granularity, in seconds. Match appmeta/settings.json. */
export const DURATION_MIN = 5;
export const DURATION_MAX = 59 * 60 + 55;
export const DURATION_STEP = 5;
export const DURATION_DEFAULT = 30;

/** Quick clicks closer together than this count as turning fast. */
export const FAST_TURN_MS = 250;
/** Quick clicks in a row before the longer step takes over. */
export const FAST_TURN_CLICKS = 4;
/** The long step lands on whole multiples of this many seconds. */
export const FAST_SNAP = 30;

/** Seconds left when the countdown starts flashing and the LED blinks. */
export const WARN_SECONDS = 5;
/** Seconds left when the countdown starts ticking, as the device's own timer does. */
export const TICK_SECONDS = 3;

/** One half of a flash: the device's own notification blink is 500 ms per phase. */
export const FLASH_MS = 500;
/** How many times the finish announcement flashes. */
export const FINISH_FLASHES = 3;
/** How long the finish announcement lasts, before the app returns to the start screen. */
export const FINISH_MS = FINISH_FLASHES * 2 * FLASH_MS;

/** Clamps a stored or encoder-set duration to a whole step inside the bounds. */
export function normalizeDuration(value: unknown): number {
  const seconds = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(seconds)) return DURATION_DEFAULT;

  const stepped = Math.round(seconds / DURATION_STEP) * DURATION_STEP;
  return Math.min(DURATION_MAX, Math.max(DURATION_MIN, stepped));
}

/** Whole seconds left. Rounded up, so 700 ms reads as 1 and only 0 reads as 0. */
export function secondsLeft(remainingMs: number): number {
  return Math.max(0, Math.ceil(remainingMs / 1000));
}

/**
 * The duration after one encoder click. A quick burst steps to whole marks —
 * 0:30, 1:00, 1:30 — rather than adding thirty seconds to wherever the fine
 * steps happened to leave it.
 */
export function stepDuration(seconds: number, delta: number, fast: boolean): number {
  if (!fast) return normalizeDuration(seconds + delta * DURATION_STEP);

  // The next whole mark above, or the one below, so a burst lands on :00/:30.
  const snapped =
    delta > 0
      ? (Math.floor(seconds / FAST_SNAP) + 1) * FAST_SNAP
      : (Math.ceil(seconds / FAST_SNAP) - 1) * FAST_SNAP;

  // Below the minimum there are no marks left; fall back to the fine step, so
  // turning down past 0:30 keeps working.
  if (snapped < DURATION_MIN) return normalizeDuration(seconds + delta * DURATION_STEP);

  return normalizeDuration(snapped);
}

/** Minutes and seconds as the device's own timer writes them, e.g. "00:30"; up to "59:55". */
export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  return `${pad(minutes)}:${pad(rest)}`;
}

function pad(value: number): string {
  return value < 10 ? `0${value}` : String(value);
}
