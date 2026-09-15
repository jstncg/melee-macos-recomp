#!/usr/bin/env python3
"""Paired phone WebSockets to native controllers over loopback UDP."""
import argparse
import asyncio
from http import HTTPStatus
import json
import math
from pathlib import Path
import secrets
import socket
import struct
from urllib.parse import urlsplit

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

HERE = Path(__file__).resolve().parent
PACKET = struct.Struct('<B6fH')


class Bridge:
    def __init__(self, udp_target, token, *, idle_timeout=2.0, players=4):
        self.target = udp_target
        self.token = token
        self.idle_timeout = idle_timeout
        self.players = players
        self.slots = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self):
        self.sock.close()

    def neutral(self, player):
        self.sock.sendto(PACKET.pack(player, 0, 0, 0, 0, 0, 0, 0), self.target)

    async def handle(self, ws):
        player = None
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), self.idle_timeout)
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError('Expected controller state.')
                requested = msg.get('p', player)
                if type(requested) is not int or not 0 <= requested < self.players:
                    raise ValueError(f'Choose a local phone port from 1 to {self.players}.')
                if player is None:
                    token = msg.get('token', '')
                    if not isinstance(token, str) or not secrets.compare_digest(token, self.token):
                        raise ValueError('Pairing expired or incorrect. Open the link printed on your Mac.')
                    if requested in self.slots:
                        raise ValueError(f'Phone port {requested + 1} is taken. Choose another port.')
                    player = requested
                    self.slots[player] = ws
                    await ws.send(json.dumps({'ok': True, 'port': player}))
                    print(f'Phone {player + 1} connected', flush=True)
                if requested != player:
                    raise ValueError('Reconnect to change phone ports.')
                axes = []
                for key in ('x', 'y', 'cx', 'cy', 'l', 'r'):
                    value = msg.get(key, 0)
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise ValueError('Controller axes must be finite numbers.')
                    axes.append(max(0 if key in ('l', 'r') else -1, min(1, value)))
                buttons = msg.get('b', 0)
                if type(buttons) is not int or not 0 <= buttons <= 1023:
                    raise ValueError('Invalid controller buttons.')
                self.sock.sendto(PACKET.pack(player, *axes, buttons), self.target)
        except (ValueError, TypeError, OverflowError) as exc:
            await ws.send(json.dumps({'err': str(exc)}))
        except (ConnectionClosed, asyncio.TimeoutError):
            pass
        finally:
            if player is not None and self.slots.get(player) is ws:
                self.neutral(player)
                del self.slots[player]
                print(f'Phone {player + 1} disconnected; controls released', flush=True)
            await ws.close()

    def http(self, connection, request):
        path = urlsplit(request.path).path
        if path == '/ws':
            return None
        if path in ('/', '/gc.html'):
            response = connection.respond(HTTPStatus.OK, (HERE/'gc.html').read_text())
            response.headers['Content-Type'] = 'text/html; charset=utf-8'
        elif path == '/health':
            response = connection.respond(HTTPStatus.OK, 'phonepad ready\n')
        else:
            response = connection.respond(HTTPStatus.NOT_FOUND, 'Not found\n')
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--udp-port', type=int, default=41234)
    args = parser.parse_args()
    token = secrets.token_urlsafe(18)
    bridge = Bridge(('127.0.0.1', args.udp_port), token)
    try:
        async with serve(bridge.handle, args.host, args.port, process_request=bridge.http,
                         max_size=4096, compression=None):
            print(f'Phone pairing: http://<your-Mac-LAN-IP>:{args.port}/#{token}', flush=True)
            await asyncio.Future()
    finally:
        bridge.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
