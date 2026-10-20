# Busy Bar Timer App

A countdown timer for the BUSY Bar, for running quiz rounds and other short timed activities. It runs on the bar itself.

![a countdown on the bar: the white rendering, the red last seconds, and the finish](docs/countdown.gif)

## Controls

| Control      | Ready             | Running         | Paused          | Finished                 |
| ------------ | ----------------- | --------------- | --------------- | ------------------------ |
| Main button  | start             | pause           | resume          | start a full countdown   |
| Encoder      | set the duration  | —               | —               | —                        |
| Back         | leave the app     | back to the top | back to the top | back to the top          |

The last seconds of a countdown flash red, with ticks and a blink of the status LED, as the bar's own timer does. At zero the finish cue plays and the app returns to its start screen — or the main button starts a fresh countdown straight away. Pausing lays the hourglass on its side until you resume.

## Installing

The app is built from source. Node 24 (see `.nvmrc`) and pnpm are required.

```sh
pnpm install
pnpm build --tgz                  # the package, in dist/
pnpm app:install --addr <host>    # omit --addr over USB
```

Once installed, launch it from the bar's apps menu. To remove it again, run `pnpm app:uninstall --addr <host>`. The bar must run firmware that includes the JavaScript app platform; the design notes explain that requirement.

## Settings

The app has a settings screen with two fields: `duration` — the countdown length, 5 seconds to 59:55 in 5-second steps — and `sound`, which turns the ticking and finish cues off and on again. The encoder changes the duration from the app's start screen as well. Both are stored on the device, so they survive a restart.

## License

MIT for everything except the two files in `src/sounds/`, which are CC-BY-SA-4.0 (© Flipper FZCO, from the BUSY Bar firmware). See `LICENSE`, `LICENSES/CC-BY-SA-4.0.txt`, and `ATTRIBUTION.md`.

How the app works — the device model it lives in, the timer's choices, and how the artwork is made — is written down in [DESIGN.md](DESIGN.md).
