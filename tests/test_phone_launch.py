import importlib.util
from pathlib import Path
import tempfile
import unittest
import contextlib
import io

ROOT = Path(__file__).resolve().parents[1]


class LaunchTests(unittest.TestCase):
    def setUp(self):
        path = ROOT/'phonepad/launch.py'
        self.assertTrue(path.exists(), 'A repo-contained phone launcher is required')
        spec = importlib.util.spec_from_file_location('phone_launch', path)
        self.launch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.launch)

    def test_profile_has_four_distinct_devices_and_preserves_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp)
            (user/'save.raw').write_bytes(b'keep save')
            self.launch.prepare_profile(user, 4)
            config = (user/'Config/GCPadNew.ini').read_text()
            for port in range(1, 5):
                self.assertIn(f'Device = SDL/0/Phone GC Port {port}\n', config)
            self.assertIn('Buttons/Z = `Shoulder R`', config)
            self.assertIn('Buttons/A = `Button S`', config)
            self.assertIn('SIDevice3 = 6', (user/'Config/Dolphin.ini').read_text())
            (user/'config.ini').write_text('volume=0.5\n')
            self.launch.prepare_profile(user, 4)
            self.assertEqual((user/'config.ini').read_text(), 'volume=0.5\n')
            self.assertEqual((user/'save.raw').read_bytes(), b'keep save')

    def test_online_uses_one_local_phone_on_both_peers(self):
        for argv in (['host'], ['join', '192.0.2.1']):
            args = self.launch.parser().parse_args(argv)
            command = self.launch.runtime_command(ROOT, ROOT/'private/test', args)
            self.assertEqual(command.count('--controller'), 1)
            self.assertEqual(command[command.index('--controller')+1], 'SDL/0/Phone GC Port 1')
            if argv[0] == 'join':
                self.assertEqual(command[command.index('--netplay-join')+1], '192.0.2.1')
            else:
                self.assertIn('--netplay-host', command)

    def test_reusing_online_profile_enables_local_ports_without_losing_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp)
            self.launch.prepare_profile(user, 1)
            path = user/'Config/Dolphin.ini'
            path.write_text(path.read_text() + '\n[Display]\nFullscreen = True\n')
            self.launch.prepare_profile(user, 4)
            text = path.read_text()
            for i in range(4):
                self.assertIn(f'SIDevice{i} = 6', text)
            self.assertIn('Fullscreen = True', text)

    def test_host_without_join_address_and_valid_ports(self):
        args = self.launch.parser().parse_args(['host', '--netplay-port', '32626'])
        self.assertEqual(args.netplay_port, 32626)
        self.assertIsNone(args.address)
        for port in ('0', '65536', '-2'):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.launch.parser().parse_args(['--web-port', port])


if __name__ == '__main__':
    unittest.main()
