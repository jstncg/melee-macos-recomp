#!/usr/bin/env python3
"""Run native Melee with paired phones, locally or in a private online match."""
import argparse
import asyncio
import configparser
import fcntl
import os
from pathlib import Path
import platform
import secrets
import signal
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def network_port(value):
    number = int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError('Port must be between 1 and 65535')
    return number


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', nargs='?', choices=('local', 'host', 'join'), default='local')
    p.add_argument('address', nargs='?', help="Host's LAN or VPN address (join only)")
    p.add_argument('--nickname', default='Player')
    p.add_argument('--netplay-port', type=network_port, default=2626)
    p.add_argument('--web-port', type=network_port, default=8000)
    p.add_argument('--udp-port', type=network_port, default=41234,
                   help='Local phone bridge UDP port; use distinct ports for two instances on one Mac')
    p.add_argument('--lan-address', help='Mac address printed in the phone pairing link')
    p.add_argument('--user-dir', type=Path, help='Separate phone-play profile; default private/phonepad/local or online')
    p.add_argument('--check', action='store_true', help='Check build outputs and port availability without launching')
    p.add_argument('--automation-dir', type=Path, help='Write native runtime diagnostic snapshots')
    p.add_argument('--audio', choices=('Cubeb', 'Null'), default='Cubeb')
    return p


def prepare_profile(user, players):
    config = user/'Config'
    config.mkdir(parents=True, exist_ok=True)
    bindings = {
        'Buttons/A': 'Button S', 'Buttons/B': 'Button E',
        'Buttons/X': 'Button W', 'Buttons/Y': 'Button N',
        'Buttons/Z': 'Shoulder R', 'Buttons/Start': 'Start',
        'Main Stick/Up': 'Left Y+', 'Main Stick/Down': 'Left Y-',
        'Main Stick/Left': 'Left X-', 'Main Stick/Right': 'Left X+',
        'C-Stick/Up': 'Right Y+', 'C-Stick/Down': 'Right Y-',
        'C-Stick/Left': 'Right X-', 'C-Stick/Right': 'Right X+',
        'Triggers/L': 'Trigger L', 'Triggers/R': 'Trigger R',
        'Triggers/L-Analog': 'Trigger L', 'Triggers/R-Analog': 'Trigger R',
        'D-Pad/Up': 'Pad N', 'D-Pad/Down': 'Pad S',
        'D-Pad/Left': 'Pad W', 'D-Pad/Right': 'Pad E',
    }
    text = ''
    for port in range(1, 5):
        text += f'[GCPad{port}]\n'
        if port <= players:
            text += f'Device = SDL/0/Phone GC Port {port}\n'
            text += ''.join(f'{key} = `{value}`\n' for key, value in bindings.items())
    # These are launcher-owned controller bindings. Save cards and graphics/audio
    # preferences in the dedicated phone profile remain persistent.
    (config/'GCPadNew.ini').write_text(text)
    dolphin = configparser.ConfigParser(interpolation=None, strict=False)
    dolphin.optionxform = str
    dolphin.read(config/'Dolphin.ini')
    if not dolphin.has_section('Core'):
        dolphin.add_section('Core')
    for i in range(4):
        dolphin.set('Core', f'SIDevice{i}', str(6 if i < players else 0))
    with (config/'Dolphin.ini').open('w') as output:
        dolphin.write(output)
    if not (user/'config.ini').exists():
        (user/'config.ini').write_text('resolution=640x528\nshow_fps_in_title=true\nfullscreen=false\n')


def runtime_command(root, user, args):
    command = [str(root/'build/runtime/moderngekko-run'),
               '--game', str(root/'private/GALE01r2'),
               '--module', str(root/'build/game/gGALE01_recomp.dylib'),
               '--user-dir', str(user), '--graphics', 'Metal', '--audio', args.audio, '--no-mods']
    if args.mode != 'local':
        command += ['--netplay-port', str(args.netplay_port), '--nickname', args.nickname,
                    '--buffer', 'auto', '--controller', 'SDL/0/Phone GC Port 1']
        command += ['--netplay-host'] if args.mode == 'host' else ['--netplay-join', args.address]
    if args.automation_dir:
        command += ['--automation-dir', str(args.automation_dir.resolve())]
    return command


def check(root, args):
    problems = []
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        problems.append('Requires Apple Silicon macOS.')
    for file in ('build/runtime/moderngekko-run', 'build/game/gGALE01_recomp.dylib',
                 'private/GALE01r2/sys/main.dol'):
        if not (root/file).is_file():
            problems.append(f'Missing {file}; run ./scripts/build_macos.sh with your disc image.')
    if not (root/'build/phonepad/gcshim.dylib').is_file():
        problems.append('Run ./scripts/setup_phonepad.sh to build the phone input bridge.')
    try:
        import websockets
    except ImportError:
        problems.append('Phone transport dependency missing; run ./scripts/setup_phonepad.sh.')
    header = root/'build/runtime/vendor/dolphin/Externals/SDL/SDL/include-config-release/build_config/SDL_build_config.h'
    if header.exists() and '#define SDL_JOYSTICK_VIRTUAL 1' not in header.read_text():
        problems.append('Runtime lacks virtual controller support; rebuild with ./scripts/build_macos.sh.')
    for kind, port, label, bind_address in (
            (socket.SOCK_STREAM, args.web_port, 'Phone web', '0.0.0.0'),
            (socket.SOCK_DGRAM, args.udp_port, 'Phone input', '127.0.0.1')):
        try:
            with socket.socket(socket.AF_INET, kind) as probe:
                probe.bind((bind_address, port))
        except OSError:
            problems.append(f'{label} port {port} is busy; stop the other phone session or choose a different port.')
    if args.mode == 'host':
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.bind(('0.0.0.0', args.netplay_port))
        except OSError:
            problems.append(f'Netplay UDP port {args.netplay_port} is busy.')
    return problems


def lan_address():
    for interface in ('en0', 'en1'):
        result = subprocess.run(['/usr/sbin/ipconfig', 'getifaddr', interface],
                                capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return socket.gethostname().split('.')[0] + '.local'


async def run(root, user, args):
    from websockets.asyncio.server import serve
    # Works both when invoked as a script and when imported by tests.
    sys.path.insert(0, str(root/'phonepad'))
    from server import Bridge
    token = secrets.token_urlsafe(18)
    players = 4 if args.mode == 'local' else 1
    bridge = Bridge(('127.0.0.1', args.udp_port), token, players=players)
    log_dir = user/'Logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    shim_log = log_dir/'phone-input.log'
    shim_log.write_text('')
    env = dict(os.environ, DYLD_INSERT_LIBRARIES=str(root/'build/phonepad/gcshim.dylib'),
               GCSHIM_UDP_PORT=str(args.udp_port), GCSHIM_LOG=str(shim_log),
               MODERNGEKKO_STATICRECOMP='1', MELEE_STRICT_NATIVE='1')
    env.pop('MELEE_FRONTEND', None)
    proc = None
    try:
        async with serve(bridge.handle, '0.0.0.0', args.web_port,
                         process_request=bridge.http, max_size=4096, compression=None):
            with (log_dir/'runtime.log').open('w') as output:
                proc = await asyncio.create_subprocess_exec(*runtime_command(root, user, args),
                          env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                # The shim binds its UDP socket after attaching the SDL devices.
                # Do not announce a usable controller until the receiver is ready.
                for _ in range(300):
                    log = shim_log.read_text()
                    if f'listening on udp 127.0.0.1:{args.udp_port}' in log:
                        break
                    if proc.returncode is not None:
                        raise RuntimeError(f'Game exited ({proc.returncode}). See {log_dir / "runtime.log"}')
                    if any(error in log for error in ('failed', 'giving up', 'invalid GCSHIM')):
                        raise RuntimeError(f'Phone input could not start. See {shim_log}')
                    await asyncio.sleep(.1)
                else:
                    raise RuntimeError(f'Phone input did not become ready. See {shim_log}')
                address = args.lan_address or lan_address()
                print(f'\nPhone pairing link: http://{address}:{args.web_port}/?players={players}#{token}', flush=True)
                print('Open this link on a phone on the same Wi-Fi as this Mac. Rotate to landscape.', flush=True)
                if args.mode != 'local':
                    print('Use My phone on each Mac. Both players click Ready in the game lobby; the host clicks Start.', flush=True)
                    print(f'Netplay UDP port: {args.netplay_port}. Your friend joins the host Mac\'s VPN or reachable address.', flush=True)
                print(f'Logs and phone-play saves: {user}\nQuit the game or press Ctrl-C here to stop.\n', flush=True)
                return await proc.wait()
    finally:
        if proc is not None and proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), 5)
            except asyncio.TimeoutError:
                os.killpg(proc.pid, signal.SIGKILL)
                await proc.wait()
        bridge.close()


async def run_with_signals(root, user, args):
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    received = signal.SIGINT

    def stop(signum):
        nonlocal received
        received = signum
        task.cancel()

    for signum in (signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(signum, stop, signum)
    try:
        return await run(root, user, args)
    except asyncio.CancelledError:
        return 128 + received
    finally:
        for signum in (signal.SIGTERM, signal.SIGHUP):
            loop.remove_signal_handler(signum)


def main():
    p = parser()
    args = p.parse_args()
    if args.mode == 'join' and not args.address:
        p.error('join requires the host Mac address')
    if args.mode != 'join' and args.address:
        p.error('Only join takes an address')
    if args.mode == 'host' and args.udp_port == args.netplay_port:
        p.error('Phone input and netplay must use different UDP ports')
    problems = check(ROOT, args)
    if problems:
        raise SystemExit('\n'.join(problems))
    if args.check:
        print('Phone-play dependencies, game files, and local ports are ready. Network reachability is not tested.')
        return 0
    user = (args.user_dir or ROOT/'private/phonepad'/('local' if args.mode == 'local' else 'online')).resolve()
    # Never rewrite the regular app's controller configuration.
    if user == (ROOT/'private/user').resolve():
        p.error('Use a separate --user-dir for phone play; private/user belongs to the regular app')
    user.mkdir(parents=True, exist_ok=True)
    with (user/'.phone-play.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('This phone profile is already running. Use a separate --user-dir.')
        prepare_profile(user, 4 if args.mode == 'local' else 1)
        try:
            return asyncio.run(run_with_signals(ROOT, user, args))
        except KeyboardInterrupt:
            return 0
        except (RuntimeError, OSError) as exc:
            raise SystemExit(str(exc))


if __name__ == '__main__':
    raise SystemExit(main())
