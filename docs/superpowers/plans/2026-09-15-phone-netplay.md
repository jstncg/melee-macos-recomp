# Phone Controllers and Private Netplay Implementation Plan

**Goal:** Let each player run Melee on an Apple Silicon Mac, pair a phone on local Wi-Fi, and host or join a private online game.

**Architecture:** Bring the existing phonepad prototype into this source-only repo. A local WebSocket server forwards full controller states over loopback UDP to SDL virtual controllers inside the native runtime. Existing netplay synchronizes the Macs; each phone connects only to its own Mac.

**Stack:** Python 3.11+, websockets, HTML/JavaScript, C/SDL3, existing ModernGekko netplay.

**Scope:** The user approved beginning implementation of this flow. Keep the current native build and game data in place on `codex/phone-netplay`. No public matchmaking, browser game port, deployment, or paid relay. Preserve the original prototype and existing saves.

## 1. Reproducible phone controller setup

- [x] Copy `gc.html` and `gcshim.c` from the existing prototype into `phonepad/`; include no binaries or virtual environments.
- [x] Add a pinned dependency file and `scripts/setup_phonepad.sh` to create the environment and build the shim.
- [x] Make the SDL virtual-joystick patch apply idempotently in the normal build, within the SDL submodule itself.
- [x] Extend source audit and CI for the new source files.

## 2. Reliable pairing and controller transport

- [x] Write real WebSocket-to-UDP tests: claimed port routes correctly; second phone cannot steal it; wrong pairing token is rejected; non-finite input is rejected; disconnect and stale connection release controls; server serves only controller assets.
- [x] Run tests against the prototype to demonstrate missing behavior, then implement the bridge.
- [x] Add session pairing links, connection errors, heartbeat, and neutral input on page hide/reconnect.
- [x] Add configurable shim UDP ports and stale-input release so two peers can be tested independently on one Mac.

## 3. Local/host/join launcher

- [x] Add `scripts/play_phones.sh` and a Python launcher accepting `local`, `host`, or `join ADDRESS`, plus nickname and network-port options.
- [x] Use isolated phone-play save/config folders. Generate all controller bindings reproducibly, use one local phone for online play, and report the assigned game port in the existing lobby.
- [x] Start the bridge, wait for readiness, launch the shim/runtime directly, and clean up only processes owned by this launch.
- [x] Add `--check` diagnostics for missing setup/build outputs and conflicting ports.

## 4. Verification and handoff

- [x] Run source tests, real bridge integration tests, C compilation, script syntax, and CPU ABI checks.
- [x] Exercise controller page connection and touch input in a browser.
- [x] Run bounded two-peer native smoke test using phone devices and independent bridge/UDP ports. Record exactly what it proves.
- [x] Refresh the app bundle from the existing runtime build.
- [x] Document setup, local play, private Host/Join over VPN or forwarded UDP, troubleshooting, and a full two-Mac match acceptance checklist.

## Later milestones

1. Human acceptance: actual phones, simultaneous inputs, controller feel, full matches across two Macs and separate networks, disconnect/rejoin behavior.
2. Optional private room codes and connectivity relay: requires choosing a hosted service; not necessary for direct Host/Join.
3. Distribution polish: fresh-Mac build verification and installer/setup UX. Each user still supplies compatible game data.


## Verification record — September 15, 2026

- 15 Python tests passed, including real WebSocket-to-UDP tests.
- SDL virtual-driver patch applied cleanly to the pinned source in a temporary checkout; reverse detection passed.
- Shim compiled with Apple Clang for ARM64; local native launch attached four distinct phone devices.
- Controller page checked at 844×390: paired successfully, no horizontal overflow, Start/A synthetic touch events reached the game and advanced first-run menus to the title screen.
- Local native status reported about 60 FPS.
- Two-peer phone/netplay smoke passed with host 609 frames at 59.94 FPS and join 612 frames at 59.94 FPS. Both bridged phone connections delivered input; teardown left no native runtime running.
- CPU ABI check passed for 49 fields.
- Source audit passed: 44 tracked source files; no excluded artifacts. Staged diff whitespace check passed.
- Refreshed the development app bundle; macOS signature verification passed.
- Code review identified terminal-termination cleanup and controller enablement when switching profile modes. Both issues were reproduced, fixed, and reviewed again with no blocking findings.
- Native SIGTERM and SIGHUP regression checks both passed: the game stopped and phone web/UDP ports were released. No test game processes remain running.

Limitations: no physical phone, second Mac, fresh full game rebuild, full match, or internet-network test was performed. Existing native build outputs were reused. Room codes, relay hosting, and standalone distribution remain later milestones.
