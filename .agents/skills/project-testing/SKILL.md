---
name: project-testing
description: "Mandatory check and live-test workflow before claiming any change is complete, and before packaging or installing the app on a BUSY Bar. Use before running checks, claiming validation is done, or live-testing on hardware."
---
# Testing and Validation

## Purpose

This project has no unit-test framework: the app's value is entirely in how it
behaves on a physical device. This skill defines what "validated" means here so
that a passing type check is never confused with working software.

## Scope

Use this skill when:

- finishing any change, before saying it is done;
- packaging (`build/tgz`) or installing the app on a BUSY Bar;
- planning a live test on hardware.

Do not use this skill for:

- platform API contracts (see `project-busy-app`);
- firmware development (out of scope for this repo).

## Mandatory Knowledge

- Toolchain prerequisites: Node.js 24 (see `.nvmrc`; apps require
  `>=24 <26`) and `pnpm`. The app is built with `@busy-app/cli`.
- Canonical commands (also in `AGENTS.md`):
  - `pnpm typecheck` — TypeScript only; catches type drift in settings,
    display elements, and API payload shapes.
  - `pnpm build` — produces the package folder.
  - `pnpm build --tgz` — also packs `dist/<app-id>.tgz`.
  - `pnpm app:install --addr <host>` — stages and installs the package
    (omit `--addr` over USB).
  - `pnpm app:run --addr <host>`, `pnpm app:stop --addr <host>`,
    `pnpm app:uninstall --addr <host>`.
- The app runs on-device; the device must be reachable. Over USB no password is
  needed; over Wi-Fi the HTTP API must be enabled and, if password protection
  is on, `--password` must be passed.
- Two bars on one host are ambiguous by address: each USB link gives the host
  `10.0.4.21/24` while the bar itself is `10.0.4.20`, so two connected bars
  both answer to `10.0.4.20` and the kernel picks one non-deterministically.
  Before installing or live-testing, pin the target — unplug the other bar, or
  force a route (`sudo ip route replace 10.0.4.20/32 dev <iface>`) — and
  confirm it is the intended device (`/api/status`, `usb_mac`) before acting.
  Evidence: `busy-app/busy-tools @ efbc7e93c889`,
  `packages/cli/src/lib/device.ts`.
- **The app can be driven without hands.** `POST /api/input?key=<start|back|up|down|ok>`
  sends a key press, so every state can be exercised from the workstation:
  verified 2026-10-15 by running a whole countdown — start, pause, resume, back
  and the finish's automatic return — and reading each state off `/api/screen`.
  Matching the icon region against `src/images/*.png` even identifies which
  frame is drawn. `up` and `down` address the encoder — one call is one turn,
  which the runner reports to the app as `{key: 'encoder', delta: ±1}` — and
  `ok` is the encoder's push, so the encoder path is drivable too. Keep the capture's colour caveat in mind (see
  `project-busy-app`): brightness and geometry are faithful, colours are not.
  Evidence: `busy-app/busybar-firmware @ d3869762c768`,
  `applications/services/web_server/openapi/input.yaml`,
  `applications/services/js_runner/js_input.c`.
- Flashing a dev firmware onto a bar needs BOTH processors in step: the U5
  (main) and the Si917 (wireless/radio). The intercom handshake exchanges a
  git-hash-derived control string, so a U5-only flash against an older Si917
  leaves the bar showing "System error, restart device" with input locked and
  Wi-Fi/BLE/MQTT dead. The README's `./fbt flash_usb` is U5-only — use
  `./fbt flash_usb_full_unsigned` (resources + Si917 M4 + Si917 NWP, unsigned)
  so both sides share one build. The *signed* `flash_usb_full` needs
  `SI917_SIGN_KEYSTORE` or a signing service.
- Fallback when the Si917 cannot be updated (no signing keys, secured part) —
  VERIFIED on 2026-10-15: build the U5 to expect the Si917's version, then
  flash without the tool's pre-flight version check.
  `./fbt flash_usb INTERCOM_FORCE_VERSION=<si917 git hash>` builds the bundle
  with that control string compiled in (confirm it is really there:
  `grep -a <hash> fbt_layers/fbtng/build/f22-firmware-D/firmware.elf`), but
  its own guard aborts — by design it compares the forced value against the
  bar's *current* `intercom_version`, which cannot match on the first switch.
  Post the built `.tgz` straight to `/api/update` instead:
  `curl -X POST --data-binary @<bundle.tgz> http://10.0.4.20/api/update`
  (match the tool: `Content-Type: application/x-www-form-urlencoded`; add
  `--interface <usb-iface>` when more than one bar is attached). The bar
  answers `{"result":"OK","message":"Update accepted..."}`, reboots, and
  comes back with `intercom_version` equal to the forced value.
  `INTERCOM_DISABLE_VERSION_CHECK` only works when BOTH processors set it, so
  it cannot help against a firmware you cannot rebuild.
- An unsigned bundle that *does* carry Si917 images (`flash_usb_full_unsigned`)
  was accepted by the flasher but rejected on the bar ("Update failed" on its
  display) — the leading, unconfirmed cause being the Si917 bootloader
  refusing an unsigned image. Prefer the forced-version route above unless
  signing is available.
- Evidence: `busy-app/busybar-firmware @ 63f20dd931ef` (the build a bar under
  test ran): `project.scons`, `applications/services/intercom/intercom.c`,
  `intercom_sync.c`, `scripts/fbt_env_modules/bsbdist/update.scons`,
  `scripts/update_over_http.py`, `documentation/Build System.dox.md`.

## Best Practices

- Treat `typecheck` + `build` as the minimum bar, never as validation of
  behavior.
- Test on hardware for every state and every control that the change touches;
  the device is the only environment where input, display, audio, and settings
  actually run.
- Re-install before testing when resource files (sounds, images) changed: the
  package install replaces the app directory.
- Keep a scratch list of what was exercised on which firmware/API version.

## Bad Practices

- Claiming a feature works because `typecheck` passes.
- Testing only the happy path; the timer's value is in its edge behavior
  (pause mid-flash, back at each state, restart after finish).
- Leaving a test app installed in a half-broken state without telling the user.
- Assuming the emulator matches the device for audio and LED behavior.

## Workflow Checklist

1. `pnpm typecheck`.
2. `pnpm build` (add `--tgz` when preparing an install).
3. Install: `pnpm app:install --addr <host>` (omit `--addr` over USB).
4. Launch: `pnpm app:run --addr <host>`.
5. Walk the live checklist below for the affected behavior.
6. Record the result (what was run, on which device/API version, what was seen)
   in the active SOW's Validation section.

## Validation Checklist

Live checklist, at minimum for a release-grade change:

- install succeeds and the app appears in the apps menu;
- launch shows the expected initial state;
- main button press/release drives start, pause, and resume as designed;
- back behaves as designed in every state;
- countdown reaches zero and the finished state is unmistakable;
- pause and resume do not drift the remaining time;
- encoder changes the configured duration and the value survives an app restart;
- flashing cue and LED behave as designed;
- sounds play at the designed moments (tick near the end, finish at zero);
- stopping the app (or `pnpm app:stop`) leaves the device clean.

Before claiming done:

- typecheck and build were re-run after the last edit;
- the live checklist covered every behavior the change touched;
- any check that could not be performed is reported with the reason;
- specs/skills updated if a contract changed.

## Evidence

- `busy-app/busy-tools @ efbc7e93c889`: `packages/cli/src/commands/app.ts`,
  `packages/cli/src/lib/build.ts`.
- `busy-app/clock-app @ 6282324290f3`: `package.json` scripts
  (`typecheck`, `build`, `build/tgz`, `app:*`).
- `SOW-0001`: acceptance criteria the live checklist enforces.

## Update Rules

Update this skill when:

- a new canonical command or device workflow appears;
- a live test finds a failure that typecheck/build could not;
- the user corrects the validation workflow;
- a reviewer finds a repeated validation mistake.
