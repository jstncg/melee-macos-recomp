# Phones as Melee controllers

Each player runs Melee on an Apple Silicon Mac and opens a controller page on a phone connected to that Mac's Wi-Fi. The Macs connect through Melee's private netplay. The phone controls the game on its own Mac; it does not display or stream the game.

## Setup

Requirements: Apple Silicon, macOS 14+, Python 3.11+, Apple developer tools, and the native game built from your own Melee USA revision 2 disc. Follow the main README for the native build first.

```sh
./scripts/setup_phonepad.sh
./scripts/play_phones.sh --check
```

Setup installs the pinned Python dependency into `private/phonepad-venv/` and compiles the input bridge into `build/phonepad/`. No files from another repository are required.

The regular game build now applies `patches/sdl-virtual-joystick.patch` inside the SDL submodule. Existing builds without virtual joystick support must be rebuilt with `./scripts/build_macos.sh`. If the virtual-driver patch is already applied, the build preserves it.

## Play on one Mac

```sh
./scripts/play_phones.sh local
```

Wait for the printed **Phone pairing link**. Open the entire link, including the part after `#`, on each phone. Rotate the phone to landscape, choose a different local phone port for each player, and tap Connect. Up to four phones can control one game.

The game may ask you to confirm creation of a new memory card on first launch. Press A on your phone, then Start at the title screen. Use the Mac's mouse for the netplay lobby.

## Play against a friend online

Both players need compatible native builds, their own game data, and a Mac. Each phone stays connected to its own Mac over local Wi-Fi.

**Host:**

```sh
./scripts/play_phones.sh host --nickname Justin
```

**Friend:**

```sh
./scripts/play_phones.sh join HOST_ADDRESS --nickname Friend
```

Replace `HOST_ADDRESS` with the host Mac's reachable address:

- Same network: use the host's LAN address.
- Different networks: connect both Macs to a shared VPN that permits connections between peers, then use the host's VPN address. Alternatively, forward UDP **2626** on the host's router to the host Mac and use the host's reachable public address. Port forwarding may not work behind carrier-grade NAT.
- `127.0.0.1` works only when both game instances are on the same computer.

Each player opens the pairing link printed on **their own Mac** and selects My phone. Both use local phone port 1; the netplay lobby assigns the match player numbers. Keep the lobby's selection at **Phone GC Port 1**, click **Ready** on both Macs, then **Start** on the host.

For a different game port, both sides pass the same `--netplay-port NUMBER`. That is distinct from the phone web port, which defaults to TCP 8000. Only the game connection crosses the internet. Do not forward the phone web port or use a friend's pairing link remotely: it controls the wrong Mac and does not provide a game display.

Netplay currently uses input delay. Rollback, private room-code coordination, and a hosted relay are separate future work. Full matches across separate Macs and internet connections still require testing.

## Controls

- Movement: left touch stick, relative to where your thumb lands.
- A: attack/confirm; B: special/back; X: jump.
- L/R: shield; Z: grab; Start: start/pause.
- Yellow directions: C-stick cardinal directions.

This is a simplified touch layout: Y and D-pad buttons are not exposed, C-stick directions are digital, and L/R are full-press triggers. Touch controls suit casual play; simultaneous inputs, analog precision, and latency should be evaluated on your actual phone.

The page sends full input states on changes plus a heartbeat every 250 ms. A disconnected or stalled sender releases input; the native bridge also releases input after one second without packets. Returning from a backgrounded phone tab reconnects with neutral controls.

## Saves, logs, and stopping

Phone play has its own persistent profiles, so the regular app's saves/configuration stay intact:

- Local phone play: `private/phonepad/local/`
- Online phone play: `private/phonepad/online/`
- Per-profile logs: `Logs/runtime.log` and `Logs/phone-input.log`

Quit the game or press Ctrl-C in the launch terminal. The launcher stops its own game process and phone server. Only one launch may use a given profile at a time.

Advanced options: `--web-port`, `--udp-port`, `--lan-address`, `--user-dir`, and `--automation-dir`. For two sessions on one Mac, use distinct web ports, phone UDP ports, and user directories; both peers still use the same netplay port.

## Troubleshooting

- **Phone cannot open the page:** both devices must be on the same reachable LAN. Guest Wi-Fi/client isolation can block access. Allow the launcher/Python through the Mac firewall for local connections. If the printed IP is wrong, pass `--lan-address YOUR_MAC_LAN_IP`.
- **Pairing incorrect/expired:** reopen the complete link from the current launch, including its `#` token. Restarting creates a new pairing token.
- **Port taken:** choose another phone port for couch play. Online play accepts one local phone per Mac.
- **Controls never connect to the game:** inspect `Logs/phone-input.log`; it should show four attached virtual pads and a listening loopback UDP port. Rebuild the runtime if SDL virtual joystick support is missing.
- **Host/Join stalls:** verify matching builds, game data, the address, UDP port, and VPN/router configuration. `--check` checks local setup; it does not prove internet reachability.

The pairing token prevents other devices casually claiming a controller. The controller page is served over plain HTTP for local Wi-Fi use; do not expose this development server publicly.

## Developer checks

```sh
private/phonepad-venv/bin/python -m unittest discover -s tests
private/phonepad-venv/bin/python scripts/test_phone_netplay.py
private/phonepad-venv/bin/python scripts/test_phone_shutdown.py
```

The netplay check requires the native build and game data. It starts two peers with isolated saves and independent phone bridges, pairs WebSocket clients, sends input, and requires 600 game frames on both peers. Evidence stays in `private/phone-netplay-test-*/`. It proves local boot/input transport, not full-match synchronization or internet latency. The shutdown check starts isolated native sessions and verifies that SIGTERM and terminal hangup stop the game and release both phone-server ports.

### Two-Mac acceptance test

1. Set up from the repo on both Macs and run `--check`.
2. Pair actual phones; verify movement, A/B/X/Z/Start, both shields, and all C-stick directions.
3. Host/Join on a LAN, verify one controller belongs to each player, then finish a match.
4. Repeat across different networks via VPN or forwarded UDP; record match completion, visible delays, and any divergence between screens.
5. Background/disconnect each phone while holding input. Check that the fighter releases the action and reconnecting works.
6. Disconnect one Mac during a match. Check the other returns to a usable state and a fresh Host/Join can start again.

## Origin

Adapted from the local `wiicompiled/phonepad` prototype into this repository. Source files are included; compiled bridges, environments, private game data, and test captures are excluded from Git.
