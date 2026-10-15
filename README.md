# Busy Bar Timer App

A countdown timer for the BUSY Bar, for running quiz rounds and other short
timed activities. The app is `net.ralphm.timer`.

## Controls

| Control      | Ready             | Running         | Paused          | Finished                 |
| ------------ | ----------------- | --------------- | --------------- | ------------------------ |
| Main button  | start             | pause           | resume          | start a full countdown   |
| Encoder      | set the duration  | —               | —               | —                        |
| Back         | leave the app     | back to the top | reset           | back to the top          |

The time reads like `00:30`, with the app's own hourglass beside it. During the
last five seconds it flashes red and the status LED blinks along; the last
three seconds also tick, as the device's own timer does. At zero the finish cue
plays, `DONE` flashes three times in step with the LED, and the app returns to
its start screen by itself — or the main button starts a fresh countdown
straight away. While the countdown runs the colon blinks.

The encoder takes 5-second steps. A burst of quick clicks steps to whole
half-minutes instead — `00:30`, `01:00`, `01:30` — so the whole range stays
reachable without the value landing anywhere odd.

## Getting started

Node 24 (see `.nvmrc`) and pnpm are required.

```sh
pnpm install
pnpm typecheck
pnpm build                 # the package folder, in dist/
pnpm build --tgz           # also dist/net.ralphm.timer.tgz
pnpm app:install --addr <host>   # omit --addr over USB
pnpm app:run --addr <host>
```

The JS app platform is young: the device must run firmware that includes
`js_runner` and the `/api/apps/*` API. Release 1.2.4 and everything before it
predate that, so installing onto a device on a release build answers with
HTTP 405.

## Settings

`src/appmeta/settings.json` gives the app a settings screen with two fields:
`duration` — 5 to 3595 seconds (`00:05` to `59:55`), in 5-second steps — and
`sound`, which turns the ticking and finish cues off and on again, on by
default. The encoder changes the duration from the app's start screen as well,
and both are stored on the device, so they survive a restart.

## Sounds

`src/sounds/` carries the BUSY Bar's own countdown cues. They are shipped with
the app rather than taken from the device, so no setup step is needed. See
`ATTRIBUTION.md` for their origin and license.

## Artwork

`src/images/` holds the hourglass beside the time: one frame per step of its
drain, drawn by `tools/make-icon.py`. The idle screen shows it spent, starting a
countdown turns it over, and it drains as the time runs down.

The frames are drawn at their final size with hard edges — on an LED matrix a
half-lit pixel reads as a dim lamp, so there is nothing for antialiasing to
smooth. The same script draws the two icons the apps menu shows
(`src/appmeta/icon_front_8x8.png` and the back display's), with the same glass
and sand: empty above, filled below.

## License

MIT for everything except the two files in `src/sounds/`, which are
CC-BY-SA-4.0 (© Flipper FZCO, from the BUSY Bar firmware). See `LICENSE`,
`LICENSES/CC-BY-SA-4.0.txt`, and `ATTRIBUTION.md`.
