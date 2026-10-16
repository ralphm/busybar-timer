# Busy Bar Timer App

A countdown timer for the BUSY Bar, for running quiz rounds and other short
timed activities. It runs on the bar itself — no phone, no network — and shows
the time in large digits with an hourglass beside it that drains as the
countdown runs. The app is `net.ralphm.timer`.

![a countdown on the bar: the white rendering, the red last seconds, and the finish](docs/countdown.gif)

## Controls

| Control      | Ready             | Running         | Paused          | Finished                 |
| ------------ | ----------------- | --------------- | --------------- | ------------------------ |
| Main button  | start             | pause           | resume          | start a full countdown   |
| Encoder      | set the duration  | —               | —               | —                        |
| Back         | leave the app     | back to the top | back to the top | back to the top          |

The time reads like `00:30`. During the last five seconds it flashes red and the
status LED blinks along; the last three seconds also tick, as the bar's own
timer does. At zero the finish cue plays, `DONE` flashes three times in step
with the LED, and the app returns to its start screen by itself — or the main
button starts a fresh countdown straight away. While the countdown runs the
colon blinks, and sand pours through the hourglass; pausing lays the glass on
its side — the way to stop a real hourglass — until you resume.

The encoder takes 5-second steps. A burst of quick clicks steps to whole
half-minutes instead — `00:30`, `01:00`, `01:30` — so the whole range stays
reachable without the value landing anywhere odd.

## Installing

The app is built from source. Node 24 (see `.nvmrc`) and pnpm are required.

```sh
pnpm install
pnpm build --tgz                  # the package, in dist/
pnpm app:install --addr <host>    # omit --addr over USB
```

Once installed, launch it from the bar's apps menu. To remove it again, run
`pnpm app:uninstall --addr <host>`.

The device must run firmware that includes the JavaScript app platform
(`js_runner` and the `/api/apps` API). Release 1.2.4 and everything before it
predate that, so installing onto a device on a release build answers with
HTTP 405.

## Settings

The app has a settings screen with two fields: `duration` — 5 to 3595 seconds
(`00:05` to `59:55`), in 5-second steps — and `sound`, which turns the ticking
and finish cues off and on again, on by default. The encoder changes the
duration from the app's start screen as well, and both are stored on the
device, so they survive a restart.

## License

MIT for everything except the two files in `src/sounds/`, which are
CC-BY-SA-4.0 (© Flipper FZCO, from the BUSY Bar firmware). See `LICENSE`,
`LICENSES/CC-BY-SA-4.0.txt`, and `ATTRIBUTION.md`.

How the app works — the device model it lives in, the timer's choices, and how
the artwork is made — is written down in [DESIGN.md](DESIGN.md).
