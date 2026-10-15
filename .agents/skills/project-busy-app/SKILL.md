---
name: project-busy-app
description: "Mandatory platform knowledge before writing or changing app code that talks to the BUSY Bar (display, audio, settings, input, storage, manifest, settings schema) or before packaging/installing the app. Use before editing src/main.ts, src/frame.ts, settings/manifest files, or any device API call."
---
# BUSY Bar App Platform

## Purpose

Prevents re-deriving (and mis-remembering) the BUSY Bar device contracts. The
app runs on-device in a limited JavaScript runner; several APIs differ from what
a browser or Node developer would expect. Getting these wrong produces silent
failures on hardware that neither `typecheck` nor `build` can catch.

## Scope

Use this skill when:

- writing or changing app code that calls any device API;
- changing `src/appmeta/manifest.json` or `src/appmeta/settings.json`;
- adding resources (images, animations, sounds, fonts) to the app;
- changing how the app is packaged or installed.

Do not use this skill for:

- the host-side toolchain workflow (see `project-testing`);
- firmware or device internals beyond the API contract.

## Mandatory Knowledge

### Identity, packaging, install

- App id is a reverse-DNS name; this project uses `net.ralphm.timer`.
- `src/appmeta/manifest.json`: `format_version: 1`, `id`, `name`, `version`,
  `api_version`, `description`, `author`.
- `api_version` must NOT be newer than the target device's `api_semver`
  (read it from `GET /api/status`): install and launch refuse a newer value
  with "API version mismatch". The upstream checkout can be newer than the
  device — pin to the device, not to the checkout.
  Evidence: `busy-app/busybar-firmware @ d3869762c768`,
  `applications/services/web_server/web_server.c`,
  `applications/services/web_server/http_api/api_apps.c`.
- Other manifest shape: Evidence: `busy-app/clock-app @ 6282324290f3`,
  `src/appmeta/manifest.json`.
- `src/appmeta/settings.json`: `format_version: 1`, `version`, `fields{}`.
  Field types seen in the platform: `boolean`, `integer` (`min`, `max`, `step`),
  `string`, `enum` (`options[]` with `value`/`label`), `color`, `time`, `geo`,
  `group`.
- The build packs `<id>/appmeta/`, `<id>/scripts/main.js`, and resource folders
  (`images/`, `animations/`, `sounds/`, `fonts/`) into a `.tgz`.
- The JS app platform is firmware-gated. `js_runner` and the `/api/apps/*` API
  (including `/api/apps/stage` for installs) exist only in firmware builds
  that include them. As of 2026-10-15 no release tag does — `js_runner` first
  landed on `dev` (`917ee91f`, 2026-07-29) and `api_apps.c` on `dev`
  (`00b41922`, 2026-09-17) — so on a device running release 1.2.4 an install
  fails with HTTP 405. Check the target device's firmware before planning an
  install or promising a live test. Evidence:
  `busy-app/busybar-firmware @ d3869762c768`,
  `applications/services/web_server/http_api/api_apps.c`.
- Install is two calls: `POST /api/apps/stage` (upload the package) then
  `POST /api/apps/install`. The device unpacks the package into
  `/ext/user_assets/<app_id>/` — evidence: `/ext/user_assets/app.busy.js_example`
  contains `appmeta/` and `scripts/` on the device. This is also why
  `audio/play` with `path:` resolves inside the app's own directory.

### Runtime model

- The runner executes `scripts/main.js` from top to bottom. Nothing runs by
  itself; when the script returns (or the app is stopped), the launcher
  Start/Setup screen (the system `js_app_launcher` app) is shown again and the
  app's drawn elements are cleared.
- The Start/Setup screen belongs to the launcher, not the app. The app's code
  runs in the Run scene only.
- Globals available in the app: `fetch`, `listen`, `setInterval`/`setTimeout`/
  `clearInterval`/`clearTimeout`, `console`, `localStorage`. There is no
  `Settings` global.
- The device address is compiled in at build time (`busy-cli build --addr`);
  the template's `shared/device.ts` builds API URLs from it and defaults to the
  USB address (`localhost`).

### Settings

- There is NO `Settings` global in the runner: `js_stubs.c` stubs only
  `AbortController`, `DOMException` and `FormData`. The template's
  `@shared/settings.ts` reads `globalThis.Settings` defensively, so it returns
  null on current firmware — do not rely on it for persistence.
- App settings are read and written over HTTP:
  `GET/PUT/DELETE /api/apps/settings?app_id=<id>` (busy-lib:
  `device.AppsSettingsGet/AppsSettingsSet/AppsSettingsReset`). The stored
  document is `{version, values}`, as the device's own
  `/ext/apps_data/<app>/settings.json` files show.
- Normalize the returned values against `appmeta/settings.json` defaults
  before use; a stored document can be partial or stale after a schema
  change.

### Input

- Subscribe with `listen("input", handler)`; it returns an unbind function.
  The event union is declared in `types/env.d.ts` and produced by
  `js_input.c`: `{key: 'encoder', action: 'clockwise' | 'counterclockwise',
  delta: 1 | -1}` and `{key: 'ok' | 'start' | 'back', action: 'press' |
  'release'}`. The runner also forwards `short`/`long`/`repeat` button
  actions, so match on `action === 'press'` deliberately.
- This app's mapping: the large main button is `start`, the side button is
  `back`, the round encoder changes the duration, and `ok` is unused.
  Evidence: `applications/services/js_runner/js_input.c` (`InputKeyStart` →
  `start`, `InputKeyBack` → `back`, `InputKeyUp`/`Down` → `encoder`).

### Display

- Draw with `POST /api/display/draw`: `{application_name, priority, elements}`.
  `priority` 1–100; a draw at or above the running app's priority takes the
  screen.
- Element types include `text`, `image`, `animation`, `countdown`, `rectangle`,
  `xpmbitmap`; text supports fonts such as `tiny`, `small`, `normal`,
  `condensed`, `bold`, `large`, `extra_large`, and colors as `#RRGGBBAA`.
- `image`/`animation` elements accept `stock_path` with the same
  shared-only basename rule as audio (see above): only `shared/images/` and
  `shared/animations/` are reachable.
- The status LED is driven from the same payload via `led_notification_color`
  (`#RRGGBBAA`). That colour runs the status-lights **Notification preset**,
  which is a *finite* blink: `period_ms = 500`, `repeat_count = 6` → three
  blinks over ~3 s (`applications/services/status_lights/presets/blink.c:43`).
  Every draw carrying the colour **restarts** that sequence, so cueing it on
  every frame of a fast flash keeps it in its first phase and the LED looks
  steady. Cue it once per announcement instead (evidence: the 2026-10-15
  "static red" report).
- Draws are additive per element id: the device keeps whatever the app drew
  before unless the same id is drawn again or `DELETE /api/display/draw`
  removes it. Keep element ids stable across frames, or the previous frame's
  elements stay on screen.
- `DELETE /api/display/draw` clears the app's elements (the launcher also
  clears them when the script ends).
- Redraw only when the frame content actually changes; the device screen is
  small and the runner is single-threaded (see the clock app's `shownFrame`
  guard).
- While the JS runtime allocates a heap and starts the script, the launcher
  shows a spinner and "Loading..." on both displays
  (`js_app_launcher_scene_run.c`). The first draw with a priority at or above
  the launcher's takes the screen, so an app that loads settings over HTTP
  before its first draw leaves a visible blank gap — draw the default first.
- **Keep the script small, or the app starts noticeably slower than the
  built-ins.** The Loading screen lasts until the script has been parsed and
  linked (`js_runner.c`, `run_file_cmd_handler`: read → `jerry_parse` →
  `jerry_module_link` → `ScriptStarted`), so a library import dominates it.
  Importing `@busy-app/busy-lib` inlined ~36 KB of layout engine *and the font
  maps* and was measurably slower to start than the built-in clock app, which
  imports nothing; emitting display elements directly and using plain `fetch`
  cut the script to ~3 KB and matched the clock's start (656 ms vs 607 ms,
  launch → first painted frame, measured 2026-10-15). Prefer hand-built
  elements and `fetch` unless the layout engine is really needed.
- Elements can be positioned absolutely, which is how a fixed icon is kept
  independent of variable-width text: give the element `x`/`y` and an `align`
  anchor (e.g. `align: "center"` with `x` at the centre of the area to use).

### Audio

- `POST /api/audio/play` takes `{application_name, path}` OR
  `{application_name, stock_path}` (exactly one).
  - `path` resolves to `/ext/user_assets/<application_name>/<path>`.
  - `stock_path` keeps only the text after the LAST `/` and re-roots it:
    audio → `/ext/apps_assets/shared/sounds/<basename>`; images and
    animations use the same parser → `shared/images/` and
    `shared/animations/`. The tree prefix is discarded, so stock assets
    outside `shared/` are unreachable, and a `stock_path` with no `/` is
    rejected (400).
  - The public busylib-py stock-assets guide claims the tree is respected and
    lists `busy/sounds/...` entries; the device code disagrees. Verify stock
    behavior against the firmware version the device runs, not the guide.
  - Evidence: `busy-app/busybar-firmware @ d3869762c768` (same parser in
    release 1.2.4, commit `b315346d`),
    `applications/services/web_server/http_api/api_audio.c`,
    `api_display.c`, `applications/services/storage/storage.h`.
- `DELETE /api/audio/play` stops playback; volume is `GET/PUT /api/audio/volume`.
- Runtime `.snd` files carry no container magic: the bytes start directly with
  samples (verified by reading a device's own sounds). The firmware builds them
  from `.wav` sources with `scripts/audio.py` (ffmpeg-based). The Au-header
  `.snd` in the firmware's test assets is NOT the runtime format, so do not
  hand-author `.snd` files: ship ones produced by the firmware pipeline or
  taken from a device.
- An app's own sounds travel inside its package and unpack to
  `/ext/user_assets/<id>/sounds/`, so they play with
  `path: "sounds/<file>.snd"` and need no device-side setup. The app's own
  images unpack to `/ext/user_assets/<id>/images/` and are drawn the same way
  with `path: "images/<file>.png"`.
- The cues of the device's own timer, for reference: it ticks when the
  remaining seconds are `<= 3` and plays the finish cue at `0`, evaluated once
  per second — so three ticks, not one per second of a longer warning.
  Evidence: `applications/main/busy/scenes/busy_scene_timer.c`
  (`COUNTDOWN_THRESHOLD_S = 3`).
- Font widths are NOT uniform. Only `bold`, `condensed`, `normal` and
  `superscript` have equal-width digits; `extra_large` and `large` do not
  (`1` advances 5 px against 8 px for the other digits), so a changing number
  visibly shifts. Draw one character per element in fixed slots to stop the
  jitter, or pick a tabular font. `extra_large` metrics, read from the device's
  glyph tables: digits advance 8, colon 3, ink starts 2 px below the line top
  and is 10 px tall.
- The device's own clock dims its colon (`#FFFFFF66`) on alternate seconds
  rather than hiding it; that reads far better than removing the glyph.
  Evidence: `busy-app/clock-app @ 6282324290f3`, `src/frame.ts`, `src/font.ts`.
- In-app icons can come from the device's own stock images at no asset cost.
  `shared/images/` holds 84 of them: the 66 `dt_*` sticker images are 16×16 and
  colourful, the rest are small glyphs (`hourglass_5x5`, `clock_5x5`,
  `start_11x11`, …). Verified on the bar, 2026-10-15: a raw image element with
  `stock_path: "shared/images/dt_study.image"` renders as drawn, and needs no
  size — the device knows each image's dimensions.
- **PNG images drawn by an app come out with red and blue exchanged.** Verified
  on a device: a file pixel of `232,112,26` rendered as `25,109,227`. Compensate
  by swapping the channels in the shipped file, or sidestep it by using the
  device's own stock images. The apps-menu icons (`appmeta/icon_front_8x8.png`,
  `icon_back_11x11.png`) go through the launcher instead and are not affected —
  the built-in clock app's icon is near-greyscale, which is why this went
  unnoticed upstream.
- An image with translucent edges shows the display's black through them and
  reads as a grey halo; flatten the image onto black before shipping it.

### Storage and its hard limit

- `POST/GET/DELETE /api/storage/{write,read,list,remove,mkdir,rename,status}`,
  with any path matching `^/ext(/[a-zA-Z0-9._\-]*)*$`.
  `rename` is a **move**, not a copy — never use it to "copy" a file another
  app owns.
- LIMITATION: in the on-device runner, a `fetch` request body is coerced to a
  string (`jerry_value_to_string`) and measured with `strlen`, so the app
  CANNOT upload binary data (any NUL byte truncates; bytes above 0x7F are
  UTF-8 mangled). Responses, by contrast, support `arrayBuffer()`.
  Evidence: `busy-app/busybar-firmware @ d3869762c768`,
  `applications/services/js_runner/js_fetch.c`.
  Consequence: the app cannot self-provision binary files at runtime. Files
  must arrive via the package install or be placed by a host-side tool.

### Assets and licensing

- The firmware ships sounds under `assets/sounds/**` licensed
  **CC-BY-SA-4.0**; the firmware itself is GPL-2.0-or-later and
  `applications_js/**` is MIT. Evidence:
  `busy-app/busybar-firmware @ d3869762c768`, `REUSE.toml`.
- This repository is MIT with one recorded exception: `src/sounds/*.snd` are
  CC-BY-SA-4.0, taken from the firmware. Any further third-party asset must
  record its license the same way: an entry in the root `ATTRIBUTION.md`, the
  full text in `LICENSES/`, and a line in `LICENSE`. Keep such notes OUT of
  `src/` — the build copies anything non-source under `src/` into the app
  package.

## Best Practices

- Keep device I/O in one small module (the template's `shared/device.ts`) and
  keep pure logic (state machine, formatting) separate and testable by hand.
- Normalize settings against defaults on every load; the settings document can
  be partial or stale after a schema change.
- Guard redraws with a last-frame comparison.
- Prefer `led_notification_color` over a JS blink loop for LED flashing.
- Unsubscribe `listen` handlers and clear intervals before returning from the
  script, so a restart starts clean.

## Bad Practices

- Assuming browser semantics: request bodies are strings, and there is no
  `Blob`, `FormData`, `TextEncoder`, or file API for writing.
- Using `stock_path` for anything outside the device's `shared/sounds` folder
  (for example the built-in countdown sounds, which live under `busy/sounds`
  and are NOT reachable that way).
- Using `/api/storage/rename` to take a file that belongs to another app.
- Polling the API faster than the screen updates; the runner is
  single-threaded and the device is the server.
- Hard-coding colors or fonts that the 72x16 / 8x8 matrices cannot render
  legibly.

## Workflow Checklist

1. Confirm which device API the change touches and re-read the matching
   section above.
2. Make the change with device I/O in `shared/device.ts` and logic separate.
3. Run `pnpm typecheck` and `pnpm build` (see `project-testing`).
4. Live-test on the device for anything with a visible or audible effect.

## Validation Checklist

Before claiming done:

- `pnpm typecheck` passes and `pnpm build` produces a package.
- Every changed device call was exercised on hardware, or the reason it could
  not be is recorded.
- Asset changes respect the licensing rules above.
- Specs and this skill are updated if a contract above changed.

## Evidence

- `busy-app/busybar-firmware @ d3869762c768`: `applications/services/js_runner/js_input.c`,
  `js_fetch.c`; `applications/services/web_server/http_api/api_audio.c`,
  `api_storage.c`, `api_assets.c`; `applications/services/web_server/openapi/*.yaml`;
  `REUSE.toml`.
- `busy-app/busy-tools @ efbc7e93c889`: `packages/cli/src/lib/build.ts`,
  `packages/cli/src/commands/app.ts`.
- `busy-app/busylib-ts @ 088d58868c5a`: `src/BusyBar/methods/{Audio,Storage,Assets}.ts`.
- `busy-app/clock-app @ 6282324290f3`: `src/appmeta/settings.json`,
  `src/main.ts`, `shared/device.ts`.
- `SOW-0001`: decisions on controls, sounds, and state machine.

## Update Rules

Update this skill when:

- a device contract above changes or a new API version alters behavior;
- hardware testing disproves a stated behavior (for example the encoder key);
- the user corrects the workflow;
- a reviewer or a live test finds a missed failure mode.
