import { audioPlay, displayDelete, displayDraw, getAppSettings, setAppSettings } from "@shared/device";
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

/**
 * Loop cadence. The flash needs finer steps than the seconds it announces, and
 * the drawn second should follow the beep closely — the ear resolves timing
 * differences of around 10 ms in an isochronous sequence, so a coarse loop is
 * audible as an uneven rhythm.
 */
const TICK_MS = 25;

/** Frames of the hourglass drain, drawn by tools/make-icon.py. */
const DRAIN_FRAMES = 21;
/** The spin at the start: eight frames of the glass going over, this long each. */
const FLIP_MS = 60;
const FLIP_FRAMES = 8;
/** The pause tip: three frames of the glass going over, each this long. */
const TIP_MS = 80;
const TIP_FRAMES = 3;

/** Quiet time after the last encoder click before the duration is stored. */
const SAVE_DEBOUNCE_MS = 400;

/** The countdown cues, shipped with the app and unpacked into its sounds/ directory. */
const TICK_SOUND = "sounds/countdown_tick.snd";
const FINISH_SOUND = "sounds/countdown_finish.snd";

const SETTINGS_VERSION = 1;
/** Local mirrors of the settings, so the first frame and first cue are right. */
const CACHE_DURATION = "duration";
const CACHE_SOUND = "sound";

let state: TimerState = "ready";
let durationMs = DURATION_DEFAULT * 1000;
/** The duration the run now counting down started with, so a settings load landing mid-run cannot re-base the hourglass. */
let runDurationMs = durationMs;
/** When the countdown ends, while running. */
let endAtMs = 0;
/** What is left, while paused or between runs. */
let remainingMs = durationMs;
/** When the finish announcement began. */
let finishedAtMs = 0;
/** Whether the countdown's cues are played; on unless the settings say otherwise. */
let soundOn = true;
/** The settings document as last read, so writing one field keeps the others. */
let storedValues: Record<string, unknown> = {};
/** While now is before this, a freshly started countdown shows the glass turning. */
let flipUntilMs = 0;
/** The pause tip: when it began and when it is done, whichever way it runs. */
let tipStartMs = 0;
let tipUntilMs = 0;
/** Whether the tip in flight stands the glass back up (resuming). */
let tipResuming = false;
/** The last whole second drawn while running; a change is what fires the tick. */
let lastSeconds: number | null = null;
/** Newest frame sent, so an unchanged one costs nothing. */
let shown = "";
/** Whether the pouring overlay is on the device, so leaving the run removes it. */
let poured = false;
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
/** Pending countdown cues, each armed against the countdown's own end time. */
const cues: ReturnType<typeof setTimeout>[] = [];

const report = (err: unknown) =>
  console.error(`${APP}: ${err instanceof Error ? err.message : String(err)}`);

/** Plays one of the app's bundled sounds, unless sound has been turned off. */
function play(file: string): void {
  if (!soundOn) return;
  void audioPlay(APP, file).catch(report);
}

/** Milliseconds left in the current state. */
function remainingNow(): number {
  if (state === "running") return Math.max(0, endAtMs - Date.now());
  if (state === "finished") return 0;
  return remainingMs;
}

/** The hourglass frame for the current state. */
function iconPath(): string {
  // Idle and finished both show a spent glass: the sand has run down.
  if (state === "ready" || state === "finished") return drainFrame(DRAIN_FRAMES - 1);

  const now = Date.now();
  if(now < flipUntilMs) {
    const elapsed = FLIP_MS * FLIP_FRAMES - (flipUntilMs - now);
    return `images/hourglass-flip-${Math.min(FLIP_FRAMES - 1, Math.floor(elapsed / FLIP_MS))}.png`;
  }

  const step = drainStep();

  // Pausing lays the glass on its side — a real hourglass cannot pause any
  // other way — and resuming stands it back up. The return tip replays the
  // same frames backwards, so the glass turns the way it came.
  if (now < tipUntilMs) {
    const i = Math.min(TIP_FRAMES - 1, Math.floor((now - tipStartMs) / TIP_MS));
    const frame = tipResuming ? TIP_FRAMES - 1 - i : i;
    return `images/hourglass-tip-${frame}-${paddedStep(step)}.png`;
  }
  if (state === "paused") return `images/hourglass-side-${paddedStep(step)}.png`;

  return drainFrame(step);
}

/** The drain step the current level shows, 0 (full) up to DRAIN_FRAMES - 1. */
function drainStep(): number {
  const fraction = runDurationMs > 0 ? remainingNow() / runDurationMs : 0;
  return Math.round((1 - fraction) * (DRAIN_FRAMES - 1));
}

function drainFrame(step: number): string {
  return `images/hourglass-${paddedStep(step)}.png`;
}

function paddedStep(step: number): string {
  const clamped = Math.min(DRAIN_FRAMES - 1, Math.max(0, step));
  return String(clamped).padStart(2, "0");
}

/** The frame the device should be showing now. */
function view(): View {
  const now = Date.now();
  const seconds = secondsLeft(remainingNow());

  // The flashing turns over on the countdown's own timeline — the same moments
  // the digits change and the cues sound. Taking its phase from the wall clock
  // instead leaves it drifting against both.
  //
  // The phase is deliberately the second half of each second: the digits are
  // lit from the instant they change, so a new second is never spent invisible,
  // and the status LED — cued at that same moment — flashes with the text
  // rather than against it. The finish is anchored to its own beginning for the
  // same reason.
  const flashOn =
    state === "finished"
      ? Math.floor((now - finishedAtMs) / FLASH_MS) % 2 === 0
      : Math.floor(remainingNow() / FLASH_MS) % 2 === 1;

  return {
    state,
    seconds,
    icon: iconPath(),
    flashOn,
    // The colon turns over with the digits.
    colonLit: seconds % 2 === 0,
    // The pour starts once the glass is upright again — after the start turn
    // and after a pause tip coming back up; a glass on its side does not pour.
    pouring: state === "running" && now >= flipUntilMs && now >= tipUntilMs,
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

  // The pour rides along while it plays; leaving the run takes it off the
  // glass again, so a paused or spent hourglass does not keep pouring. The
  // delete is best effort: the platform can clear the canvas on its own, and
  // a gone element is nothing to repair.
  if (current.pouring) {
    poured = true;
  } else if (poured) {
    poured = false;
    void displayDelete(APP, ["pour"]).catch(report);
  }
}

/** One pass of the loop: settle the state, cue the sounds, redraw if the frame changed. */
async function tick(): Promise<void> {
  if (state === "running" && remainingNow() <= 0) {
    state = "finished";
    finishedAtMs = Date.now();
    ledCue = true;
  } else if (state === "finished" && Date.now() - finishedAtMs >= FINISH_MS) {
    // The flashes have been served; back to the start screen without a key press.
    reset();
  }

  const current = view();

  // The flash and the LED follow the seconds here. The beeps are scheduled
  // separately, so that they land exactly on the boundary rather than
  // whenever this loop happens to notice — see armBeeps.
  if (state === "running" && current.seconds !== lastSeconds) {
    // The blink preset is shorter than the warning, so keep it alive by
    // cueing it once per second; that reads as blinking through the window.
    if (current.seconds > 0 && current.seconds <= WARN_SECONDS) ledCue = true;
    lastSeconds = current.seconds;
  }

  const key = `${current.state}|${current.seconds}|${current.flashOn}|${current.icon}`;
  if (key === shown) return;

  const cue = ledCue;
  await draw(current, cue);
  // Only a frame the device took counts as shown; a failed draw is retried on
  // the next tick, with its LED cue still pending.
  shown = key;
  ledCue = false;
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
  const raw = cacheGet(CACHE_DURATION);
  return raw === null ? undefined : normalizeDuration(Number(raw));
}

function cachedSound(): boolean | undefined {
  const raw = cacheGet(CACHE_SOUND);
  return raw === null ? undefined : raw === "1";
}

function cacheGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch (err) {
    report(err);
    return null;
  }
}

function cacheSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch (err) {
    report(err);
  }
}

/** A stored sound flag: anything that is not a boolean means its default, on. */
function normalizeSound(value: unknown): boolean {
  return typeof value === "boolean" ? value : true;
}

/** Reads the stored settings and reconciles them with the local copies. */
async function loadSettings(): Promise<void> {
  try {
    const document = await getAppSettings(APP);
    storedValues = (document.values as Record<string, unknown> | undefined) ?? {};

    const seconds = normalizeDuration(storedValues["duration"]);
    if (seconds !== Math.round(durationMs / 1000)) {
      durationMs = seconds * 1000;
      if (state === "ready") remainingMs = durationMs;
    }
    cacheSet(CACHE_DURATION, String(seconds));

    soundOn = normalizeSound(storedValues["sound"]);
    cacheSet(CACHE_SOUND, soundOn ? "1" : "0");
  } catch (err) {
    report(err);
  }
}

/**
 * Stores the duration. The device replaces the whole document, so it is read
 * back first: a change made elsewhere — the API, or another tool — while the
 * app was running must not be overwritten with the copy read at launch. That
 * copy stays the fallback, so a failed read still stores the duration.
 * Best effort: a failed write must not break the timer.
 */
async function saveDuration(seconds: number): Promise<void> {
  let values: Record<string, unknown>;
  try {
    const document = await getAppSettings(APP);
    values = { ...((document.values as Record<string, unknown> | undefined) ?? {}) };
  } catch (err) {
    report(err);
    values = { ...storedValues };
  }
  values["duration"] = seconds;
  storedValues = values;

  await setAppSettings(APP, { version: SETTINGS_VERSION, values });
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

  cacheSet(CACHE_DURATION, String(pendingSave));
  void saveDuration(pendingSave).catch(report);
  pendingSave = undefined;
}

/**
 * Schedules every cue of the countdown against its end time.
 *
 * Each cue belongs to an absolute moment: the ticks one, two and three seconds
 * before the end, and the finish cue at the end itself. Firing them from the
 * redraw loop instead would start each one whenever the loop happened to run —
 * up to a loop period late, and not the same amount each time. The ear resolves
 * differences of about 10 ms in an isochronous sequence, so the last cue
 * landing late is audible as a stretched final interval.
 */
function armCues(): void {
  disarmCues();
  if (state !== "running") return;

  const now = Date.now();

  const finishInMs = endAtMs - now;
  if (finishInMs > 0) {
    cues.push(setTimeout(() => play(FINISH_SOUND), finishInMs));
  }

  for (let seconds = TICK_SECONDS; seconds >= 1; seconds--) {
    const inMs = endAtMs - seconds * 1000 - now;
    if (inMs <= 0) continue;
    cues.push(setTimeout(() => play(TICK_SOUND), inMs));
  }
}

/** Stops every pending cue, when the countdown pauses, resets or leaves. */
function disarmCues(): void {
  for (const timer of cues) clearTimeout(timer);
  cues.length = 0;
}

function begin(): void {
  flipUntilMs = Date.now() + FLIP_MS * FLIP_FRAMES;
  endAtMs = Date.now() + durationMs;
  runDurationMs = durationMs;
  remainingMs = durationMs;
  state = "running";
  lastSeconds = null;
  ledCue = false;
  armCues();
}

function pause(): void {
  flipUntilMs = 0;
  remainingMs = remainingNow();
  state = "paused";
  lastSeconds = null;
  ledCue = false;
  disarmCues();
  startTip(false);
}

function resume(): void {
  flipUntilMs = 0;
  endAtMs = Date.now() + remainingMs;
  state = "running";
  lastSeconds = null;
  ledCue = false;
  armCues();
  startTip(true);
}

/** Plays the pause tip: the glass going over to its side, or standing back up. */
function startTip(resuming: boolean): void {
  tipStartMs = Date.now();
  tipUntilMs = tipStartMs + TIP_MS * TIP_FRAMES;
  tipResuming = resuming;
}

/** Back to the start screen, keeping the duration. */
function reset(): void {
  flipUntilMs = 0;
  remainingMs = durationMs;
  state = "ready";
  lastSeconds = null;
  ledCue = false;
  disarmCues();
}

/** Leaves the app: clearing the loop and detaching the handler ends the script. */
function quit(): void {
  if (stopped) return;
  stopped = true;
  disarmCues();
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
    if (event.key === "back" && event.action !== "press") {
      // The device's canvas clears this app's drawing on every back short
      // press — the platform steps its layer aside for its own GUI, and the
      // launcher's "Loading..." screen sits exposed underneath. The press
      // already acted on the timer, and its repaint may have landed before
      // that clear, so re-assert the frame on the events that follow the
      // press: this repaint is issued after the clear was dispatched.
      shown = "";
      redraw();
      return;
    }
    if (event.action !== "press") return;
    if (event.key === "start") onMain();
    else if (event.key === "back") onBack();
  });

  // The locally kept settings first, so the screen never shows the default and
  // then jumps to the configured value once the settings arrive.
  const cached = cachedDuration();
  if (cached !== undefined) {
    durationMs = cached * 1000;
    remainingMs = durationMs;
  }
  const cachedSoundOn = cachedSound();
  if (cachedSoundOn !== undefined) soundOn = cachedSoundOn;

  redraw();
  void loadSettings().then(redraw).catch(report);
}

main();
