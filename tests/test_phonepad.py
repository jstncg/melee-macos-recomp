"""Exercise real WebSocket clients and observe the controller UDP boundary."""
import asyncio
import importlib.util
import json
from pathlib import Path
import socket
import struct
import unittest

try:
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve
except ImportError:
    connect = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(connect is None, 'Install phonepad/requirements.txt to test phone transport')
class PhoneTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        spec = importlib.util.spec_from_file_location('phone_server', ROOT/'phonepad/server.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(hasattr(module, 'Bridge'), 'Bridge must isolate paired sessions and UDP targets')
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(('127.0.0.1', 0))
        self.udp.setblocking(False)
        self.addCleanup(self.udp.close)
        self.bridge = module.Bridge(self.udp.getsockname(), 'test-pairing-token', idle_timeout=0.4)
        self.addCleanup(self.bridge.close)
        self.server = await serve(self.bridge.handle, '127.0.0.1', 0,
                                  process_request=self.bridge.http)
        self.addAsyncCleanup(self.stop_server)
        self.port = self.server.sockets[0].getsockname()[1]
        self.url = f'ws://127.0.0.1:{self.port}/ws'

    async def stop_server(self):
        self.server.close()
        await self.server.wait_closed()

    async def packet(self):
        data = await asyncio.wait_for(asyncio.get_running_loop().sock_recv(self.udp, 100), 2)
        self.assertEqual(len(data), 27)
        return struct.unpack('<B6fH', data)

    async def pair(self, ws, port=0):
        await ws.send(json.dumps({'p': port, 'token': 'test-pairing-token'}))
        self.assertTrue(json.loads(await ws.recv()).get('ok'))
        await self.packet()

    async def test_input_reaches_claimed_port_with_axes_clamped(self):
        async with connect(self.url) as ws:
            await self.pair(ws, 2)
            await ws.send(json.dumps({'p': 2, 'x': -0.5, 'y': 4, 'cx': -4, 'l': -1, 'r': 2, 'b': 49}))
            self.assertEqual(await self.packet(), (2, -0.5, 1, -1, 0, 0, 1, 49))
        self.assertEqual(await self.packet(), (2, 0, 0, 0, 0, 0, 0, 0))

    async def test_wrong_token_cannot_claim_port(self):
        async with connect(self.url) as ws:
            await ws.send(json.dumps({'p': 0, 'token': 'wrong'}))
            self.assertIn('err', json.loads(await ws.recv()))
        self.assertEqual(self.bridge.slots, {})
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.get_running_loop().sock_recv(self.udp, 100), .05)

    async def test_duplicate_claim_does_not_clear_original_controller(self):
        async with connect(self.url) as first:
            await self.pair(first)
            async with connect(self.url) as second:
                await second.send(json.dumps({'p': 0, 'token': 'test-pairing-token'}))
                self.assertIn('err', json.loads(await second.recv()))
            await first.send('{"p":0,"b":1}')
            self.assertEqual(await self.packet(), (0, 0, 0, 0, 0, 0, 0, 1))

    async def test_stale_connection_releases_held_input(self):
        async with connect(self.url) as ws:
            await self.pair(ws)
            await ws.send('{"p":0,"x":1,"b":1}')
            await self.packet()
            self.assertEqual(await self.packet(), (0, 0, 0, 0, 0, 0, 0, 0))

    async def test_invalid_input_releases_controller(self):
        for msg in ('{"p":0,"x":NaN}', '{"p":0,"x":"oops"}',
                    '{"p":1,"b":1}', '[]', '{"p":0,"b":-1}'):
            async with connect(self.url) as ws:
                await self.pair(ws)
                await ws.send(msg)
                self.assertIn('err', json.loads(await ws.recv()))
                self.assertEqual(await self.packet(), (0, 0, 0, 0, 0, 0, 0, 0))

    async def test_http_does_not_serve_source_files(self):
        for path, expected in (('/', 200), ('/gc.html', 200), ('/server.py', 404),
                               ('/../README.md', 404), ('/.venv/pyvenv.cfg', 404)):
            reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
            writer.write(f'GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'.encode())
            await writer.drain()
            response = await asyncio.wait_for(reader.read(), 2)
            writer.close()
            await writer.wait_closed()
            self.assertIn(f' {expected} '.encode(), response.splitlines()[0])


if __name__ == '__main__':
    unittest.main()
