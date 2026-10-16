# Third-party assets

## Countdown sounds

`src/sounds/countdown_tick.snd` and `src/sounds/countdown_finish.snd` are the
BUSY Bar's own countdown cues, copied byte for byte from the device
(`/ext/apps_assets/busy/sounds/`) so the app carries its cues with it.

- Copyright: 2024-2026 Flipper FZCO
- Source: the BUSY Bar firmware, https://github.com/busy-app/busybar-firmware,
  `assets/sounds/busy/`
- License: CC-BY-SA-4.0 — full text in `LICENSES/CC-BY-SA-4.0.txt`

These two files are the only third-party assets in this repository.
Everything else is MIT (see `LICENSE`).

This note lives at the repository root on purpose: the build copies anything
under `src/` that is not a source file into the app package, so a license note
kept next to the sounds would be shipped to the device as a resource.
