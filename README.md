# Melee macOS Recompilation

An experimental **Apple Silicon macOS** port of Super Smash Bros. Melee using
static recompilation. DolRecomp translates your locally supplied PowerPC game
executable into C; Apple Clang compiles it to native ARM64 code. ModernGekko and
its Dolphin-derived runtime supply Metal graphics, audio, input, timing, and
GameCube system services.

**This is a source-only release. You must supply your own Melee USA revision 2
disc image.** No game image, extracted assets, generated game code, compiled game
module, saves, or Nintendo artwork is included. This repository does not download
game data. It is not affiliated with or endorsed by Nintendo.

## Features

- Native ARM64 recompiled game code, with strict mode that stops uncovered CPU
  execution instead of silently falling back to JIT/interpreter execution.
- Metal graphics with persistent 1×–6× internal resolution, VSync, and fullscreen.
- Cubeb audio with a working, persistent master-volume control.
- PS5 DualSense and standard Xbox/SDL gamepad mappings, up to four player ports.
- Keyboard input remains active alongside Player 1's controller. D-pad and left
  stick both move; right stick supplies C-stick input.
- Native Home overlay: **Play, Settings, Netplay, Quit**. Escape toggles Home;
  Command-comma opens Settings.
- Memory-card saves, settings, save-state controls, and validated local disc import.
- Experimental direct-connect netplay with Host/Join, Ready/Start, compatibility
  checks, GameCube port assignment, and automatic input-buffer adjustment.

Gameplay remains approximately **60 FPS**. Higher internal resolution sharpens
3D edges; it does not add detail to movies or original textures. True 120 FPS
interpolation, rollback, public matchmaking, and cheat execution are not implemented.

## Requirements

- An Apple Silicon Mac running macOS 14 or newer. Intel Macs and iOS are not targets
  of this proof of concept.
- Apple Command Line Tools, Homebrew, Git, CMake, Ninja, and Python 3.11 or newer.
- Your own **USA revision 2** Melee ISO/GCM/CISO (`GALE01`, revision byte `2`).
  Other regions/revisions and RVZ/WBFS inputs are not supported by the import tool.
- Internet access for the initial open-source dependency download, and several GB
  of free space. Expect around 8–10 GB or more while building and testing.

## Install and build

There is no prebuilt game binary to download: each user generates it locally.

1. Install Apple's developer tools if needed:

   ```sh
   xcode-select --install
   ```

2. Install [Homebrew](https://brew.sh/) if you do not already have it. Clone this repo:

   ```sh
   git clone https://github.com/McDandle/melee-macos-recomp.git
   cd melee-macos-recomp
   brew bundle --file Brewfile
   export PATH="/opt/homebrew/bin:$PATH"
   python3 --version  # Must be 3.11 or newer.
   ```

3. Build using an absolute path to your own disc image:

   ```sh
   ./scripts/build_macos.sh "/absolute/path/to/your-melee-disc.iso"
   ```

   The script fetches pinned source dependencies, applies this project's patches,
   validates/extracts the disc, generates native code, compiles it, and creates
   `Melee macOS.app`. The original image is not modified. Compilation can take
   many minutes; the first build is substantially slower than subsequent builds.
   To reduce parallel memory use, run `JOBS=4 ./scripts/build_macos.sh "..."`.

4. Launch the app:

   ```sh
   open "Melee macOS.app"
   ```

   **Keep the app in the repository folder.** This development bundle uses the
   adjacent game data, compiled module, scripts, and installed Homebrew libraries.
   Moving only the app to Applications or copying it to another Mac is insufficient.
   It is locally ad-hoc signed, not notarized as a standalone distribution.

For subsequent builds, `./scripts/build_macos.sh` reuses the prepared local ISO.
For a CLI launch without Home, use `./scripts/run_macos.sh`.
`./scripts/package_macos.sh` refreshes the app from an already built runtime.

## Controls and settings

| Action | Keyboard | DualSense | Xbox |
|---|---|---|---|
| Move | WASD | Left stick / D-pad | Left stick / D-pad |
| Attack / confirm | J | Cross | A |
| Special / back | K | Circle | B |
| Jump | Space / U | Square / Triangle | X / Y |
| Shield | Q / E | L2 / R2 | LT / RT |
| Grab | O | R1 | RB |
| Start | Return | Options | Menu |
| C-stick | Arrow keys | Right stick | Right stick |

Pair controllers in macOS or connect by USB, then select them in Settings → Input.
Use Refresh after connecting a controller. DualSense has been user-tested; Xbox
uses the SDL standard mapping but has not been physically verified for this release.
Controller D-pad movement does not also send Melee's original D-pad taunt commands.

Settings pauses gameplay. Resume to see the new render resolution and hear the
new audio level. Home leaves the game running behind the overlay while blocking
in-game input. Melee's own menus control stocks, timers, items, and difficulty.
The macOS States menu exposes save-state commands.

Settings → General can import another compatible local image or select an
extracted game folder. A successfully validated selection applies next launch.
The initial build still requires the disc supplied on the command line.

## Netplay (experimental)

Both peers need matching builds and compatible game data.

1. Open Home → Netplay and enter a nickname and UDP port (default **2626**).
2. The host chooses **Host room**. The other player enters the host's address and
   chooses **Join room**. `127.0.0.1` is only for peers on the same computer.
3. Players select **Ready** in the lobby; the host selects **Start**.

Direct connections on a LAN use the host's LAN address. Across different networks,
UDP port forwarding or an appropriate shared VPN is needed; there is no traversal
or matchmaking service configured. Netplay uses fixed input delay, not rollback.
Starting netplay ends the current local game. The local settings overlay is disabled
in network matches to avoid pausing a peer independently. Closing the lobby returns
to Home; connection errors return to Home with a diagnostic.

Two isolated local peers have passed compatibility checks, Ready/Start, native
boot, and over 300 rendered frames each near 60 FPS. **Full matches across separate
computers and internet latency behavior remain unverified.**

## Local data and troubleshooting

- `private/user/`: memory cards, save states, and settings. Back this up.
- `private/GALE01r2/`: extracted game data; `private/GALE01r2.iso`: prepared image.
- `private/recompiled*/`: locally generated game code.
- `build/game/gGALE01_recomp.dylib`: locally compiled ARM64 game module.
- `upstream/` and `build/`: downloaded open-source dependencies and build products.
- `logs/app.log`: app output, render-target allocations, and audio-volume updates.

All of those directories are excluded from Git. Do not attach them to issues or
release archives. The executable check expects SHA-1
`08e0bf20134dfcb260699671004527b2d6bb1a45` for `sys/main.dol`; this is an executable
hash, not a full-disc hash. Scrubbed and pristine discs can have different disc hashes.

If performance falls at high resolution, lower the scale. If a strict-native
execution error occurs, report the PC/error text and your build revision without
uploading the disc or generated code. A successful build alone does not prove every
mode works. This remains a proof of concept with limited gameplay coverage.

The app uses the default macOS icon unless you supply optional local artwork at
`macos/assets/AppIcon.png` and rerun the packager. Icon artwork is ignored by Git.

## Development checks

```sh
python3 -m unittest discover -s tests
python3 scripts/audit_release.py
python3 scripts/check_cpu_abi.py  # After dependencies have been fetched/patched.
```

`scripts/test_netplay.py` is an opt-in two-peer local integration test that requires
a complete build and your local disc data. It uses separate save folders. Tests
in `tests/` use synthetic bytes and require no game image.

## Credits and license

This port builds on the work of **ExpansionPak/Hyperway, the Dolphin team,
aharonahdoot/SpecialK, MrPoloGit (Literally God), the DolRecomp contributors,
and the Melee decompilation community**. MrPoloGit's prior Melee/macOS recompilation
work and the upstream runtime/template are foundational; this project does not
claim to have created those systems from scratch. See [CREDITS.md](CREDITS.md) for
source links and pinned revisions.

Project code and patches are distributed under **GPL-3.0-or-later**, subject to
upstream per-file notices. See [LICENSE](LICENSE). Upstream dependencies are fetched
at build time and retain their own licenses. The code license grants no rights to
Melee game data, Nintendo artwork, or trademarks; those are not distributed here.
