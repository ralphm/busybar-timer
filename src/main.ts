import { audioPlay, displayDraw, getAppSettings, setAppSettings } from "@shared/device";
import manifest from "./appmeta/manifest.json";
import { elements, ledColor, type View } from "./frame.ts";
import {
  DURATION_DEFAULT,
  FAST_TURN_CLICKS,
  FAST_TURN_MS,
  FINISH_MS,
  FLASH_MS,
  normalizeDuration,
  secondsLeft,
  stepDuration,
  TICK_SECONDS,
  WARN_SECONDS,
  type TimerState,
} from "./timer.ts";

/** The name the app draws under; the device resolves its assets by this id. */
const APP = manifest.id;

/** Matches the template's draw priority; enough to own the screen as the running app. */
const PRIORITY = 50;

/** Loop cadence. The flash needs finer steps than the seconds it announces. */
const TICK_MS = 100;

/** Quiet time after the last encoder click before the duration is stored. */
const SAVE_DEBOUNCE_MS = 400;

/** The countdown cues, shipped with the app and unpacked into its sounds/ directory. */
const TICK_SOUND = "sounds/countdown_tick.snd";
const FINISH_SOUND = "sounds/countdown_finish.snd";

const SETTINGS_VERSION = 1;
/** Key under which the duration is also kept locally (localStorage is per app). */
const CACHE_KEY = "duration";

let state: TimerState = "ready";
let durationMs = DURATION_DEFAULT * 1000;
/** When the countdown ends, while running. */
let endAtMs = 0;
/** What is left, while paused or between runs. */
let remainingMs = durationMs;
/** When the finish announcement began. */
let finishedAtMs = 0;
/** The last whole second drawn while running; a change is what fires the tick. */
let lastSeconds: number | null = null;
/** Newest frame sent, so an unchanged one costs nothing. */
let shown = "";
/** Set when this frame should (re)start the device's LED blink. */
let ledCue = false;
let drawing = false;
let stopped = false;
let loop: ReturnType<typeof setInterval> | undefined;
let unbind: BusyUnbind | undefined;

/** Last encoder click, so quick clicks can take a longer step. */
let lastEncoderMs = 0;
/** Consecutive quick clicks; the long step needs a real burst. */
let fastStreak = 0;
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let pendingSave: number | undefined;

const report = (err: unknown) =>
  console.error(`${APP}: ${err instanceof Error ? err.message : String(err)}`);

/** Plays one of the app's bundled sounds. */
function play(file: string): void {
  void audioPlay(APP, file).catch(report);
}

/** Milliseconds left in the current state. */
function remainingNow(): number {
  if (state === "running") return Math.max(0, endAtMs - Date.now());
  if (state === "finished") return 0;
  return remainingMs;
}

/** The frame the device should be showing now. */
function view(): View {
  return {
    state,
    seconds: secondsLeft(remainingNow()),
    flashOn: Math.floor(Date.now() / FLASH_MS) % 2 === 0,
    // The colon blinks once a second while the countdown runs, as the clock does.
    colonLit: Math.floor(Date.now() / 1000) % 2 === 0,
  };
}

/**
 * Draws one frame. `cue` runs the device's LED notification preset for this
 * frame — it is a three-blink sequence, so cueing it on every flash redraw
 * would restart it forever and leave the LED apparently steady.
 */
async function draw(current: View, cue: boolean): Promise<void> {
  await displayDraw({
    application_name: APP,
    priority: PRIORITY,
    led_notification_color: cue ? ledColor(current) : undefined,
    elements: elements(current),
  });
}

/** One pass of the loop: settle the state, cue the sounds, redraw if the frame changed. */
async function tick(): Promise<void> {
  if (state === "running" && remainingNow() <= 0) {
    state = "finished";
    finishedAtMs = Date.now();
    play(FINISH_SOUND);
    ledCue = true;
  } else if (state === "finished" && Date.now() - finishedAtMs >= FINISH_MS) {
    // The flashes have been served; back to the start screen without a key press.
    reset();
  }

  const current = view();

  // The tick marks each of the last seconds once, at the moment it turns over.
  // It starts later than the flash, as the device's own timer does.
  if (state === "running" && current.seconds !== lastSeconds) {
    if (current.seconds > 0 && current.seconds <= TICK_SECONDS) play(TICK_SOUND);
    // The blink preset is shorter than the warning, so keep it alive by
    // cueing it once per second; that reads as blinking through the window.
    if (current.seconds > 0 && current.seconds <= WARN_SECONDS) ledCue = true;
    lastSeconds = current.seconds;
  }

  const key = `${current.state}|${current.seconds}|${current.flashOn}`;
  if (key === shown) return;

  shown = key;
  const cue = ledCue;
  ledCue = false;
  await draw(current, cue);
}

/** One pass of the loop, never two at once. */
function redraw(): void {
  if (stopped || drawing) return;

  drawing = true;
  tick()
    .catch(report)
    .finally(() => (drawing = false));
}

/** The duration the app last ran with, kept locally so its first frame is right. */
function cachedDuration(): number | undefined {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw === null ? undefined : normalizeDuration(Number(raw));
  } catch (err) {
    report(err);
    return undefined;
  }
}

/** Reads the stored duration and reconciles it with the local copy. */
async function loadDuration(): Promise<void> {
  try {
    const document = await getAppSettings(APP);
    const stored = (document.values as Record<string, unknown> | undefined)?.["duration"];
    const seconds = normalizeDuration(stored);
    if (seconds === Math.round(durationMs / 1000)) return;

    durationMs = seconds * 1000;
    if (state === "ready") remainingMs = durationMs;
    remember(seconds);
  } catch (err) {
    report(err);
  }
}

/** Keeps the duration locally, so a later start draws it before any round trip. */
function remember(seconds: number): void {
  try {
    localStorage.setItem(CACHE_KEY, String(seconds));
  } catch (err) {
    report(err);
  }
}

/** Stores the duration. Best effort: a failed write must not break the timer. */
function saveDuration(seconds: number): void {
  void setAppSettings(APP, {
    version: SETTINGS_VERSION,
    values: { duration: seconds },
  }).catch(report);
}

/** Stores the duration once the encoder has been still for a moment. */
function scheduleSave(seconds: number): void {
  pendingSave = seconds;
  if (saveTimer !== undefined) clearTimeout(saveTimer);
  saveTimer = setTimeout(flushSave, SAVE_DEBOUNCE_MS);
}

/** Writes a pending duration now, so leaving the app does not lose the last click. */
function flushSave(): void {
  if (saveTimer !== undefined) {
    clearTimeout(saveTimer);
    saveTimer = undefined;
  }
  if (pendingSave === undefined) return;

  remember(pendingSave);
  saveDuration(pendingSave);
  pendingSave = undefined;
}

function begin(): void {
  endAtMs = Date.now() + durationMs;
  remainingMs = durationMs;
  state = "running";
  lastSeconds = null;
  ledCue = false;
}

function pause(): void {
  remainingMs = remainingNow();
  state = "paused";
  lastSeconds = null;
  ledCue = false;
}

function resume(): void {
  endAtMs = Date.now() + remainingMs;
  state = "running";
  lastSeconds = null;
  ledCue = false;
}

/** Back to the start screen, keeping the duration. */
function reset(): void {
  remainingMs = durationMs;
  state = "ready";
  lastSeconds = null;
  ledCue = false;
}

/** Leaves the app: clearing the loop and detaching the handler ends the script. */
function quit(): void {
  if (stopped) return;
  stopped = true;
  flushSave();
  if (loop !== undefined) clearInterval(loop);
  // Not detached from inside the handler itself: with nothing else left the
  // unbind stops the app on the spot, while this handler is still running.
  if (unbind !== undefined) setTimeout(unbind, 0);
}

/** The main button: start, pause, resume, or — while finishing — a full countdown again. */
function onMain(): void {
  switch (state) {
    case "ready":
    case "finished":
      begin();
      break;
    case "running":
      pause();
      break;
    case "paused":
      resume();
      break;
  }
}

/** Back: from the start screen it leaves the app; anywhere else it resets to it. */
function onBack(): void {
  if (state === "ready") {
    quit();
    return;
  }
  reset();
}

/** The encoder sets the duration, and only while the countdown is not moving. */
function onEncoder(delta: number): void {
  if (state !== "ready") return;

  const now = Date.now();
  if (now - lastEncoderMs < FAST_TURN_MS) fastStreak += 1;
  else fastStreak = 0;
  lastEncoderMs = now;

  const seconds = Math.round(durationMs / 1000);
  const next = stepDuration(seconds, delta, fastStreak >= FAST_TURN_CLICKS);
  if (next === seconds) return;

  durationMs = next * 1000;
  remainingMs = durationMs;
  scheduleSave(next);
  redraw();
}

/**
 * Entry point, called at the end of the file: the device runs this script from
 * top to bottom and starts nothing by itself.
 */
function main(): void {
  loop = setInterval(redraw, TICK_MS);

  unbind = listen("input", (event) => {
    if (stopped) return;
    if (event.key === "encoder") {
      onEncoder(event.delta);
      return;
    }
    if (event.action !== "press") return;
    if (event.key === "start") onMain();
    else if (event.key === "back") onBack();
  });

  // The locally kept duration first, so the screen never shows the default and
  // then jumps to the configured value once the settings arrive.
  const cached = cachedDuration();
  if (cached !== undefined) {
    durationMs = cached * 1000;
    remainingMs = durationMs;
  }

  redraw();
  void loadDuration().then(redraw).catch(report);
}

main();
