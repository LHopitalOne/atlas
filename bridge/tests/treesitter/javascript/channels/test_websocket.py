import unittest

from atlas_bridge.core.http import Protocol

from .support import Channels

WS = Protocol.WEBSOCKET


class WebSocketClientTest(unittest.TestCase):
    def test_browser_socket_kept_in_a_field_connects_then_sends(self):
        found = Channels.of(
            "const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:4000/live';\n"
            'export class Live {\n'
            '  private ws?: WebSocket;\n'
            '  open() {\n'
            '    this.ws = new WebSocket(`${WS_URL}?user=${this.user}`);\n'
            '  }\n'
            '  push(frame) {\n'
            '    this.ws?.send(JSON.stringify(frame));\n'
            '  }\n'
            '}\n',
            'src/live.ts',
        )
        self.assertEqual(
            found.calls,
            [(WS, 'CONNECT', '/live', 'src/live.ts', 5), (WS, 'SEND', '/live', 'src/live.ts', 8)],
        )
        self.assertTrue({'WS_URL', 'Live', 'open', '127.0.0.1'} <= found.call('/live').hints)

    def test_ws_package_socket_in_a_variable(self):
        found = Channels.of(
            "import WebSocket from 'ws';\n"
            "const url = process.env.FEED_URL || 'ws://feed:9000/v1/feed';\n"
            'export function start() {\n'
            '  const socket = new WebSocket(url);\n'
            "  socket.on('open', () => socket.send('hello'));\n"
            '}\n',
        )
        self.assertEqual([(m, p) for _, m, p, _, _ in found.calls], [('CONNECT', '/v1/feed'), ('SEND', '/v1/feed')])

    def test_sends_on_other_objects_and_unknown_urls_are_not_channels(self):
        found = Channels.of(
            'function f(res, url) {\n'
            "  res.send('ok');\n"
            '  const s = new WebSocket(url);\n'  # a parameter nobody fills in: no channel
            "  s.send('x');\n"
            '}\n'
            "class X { open() { this.ws = new WebSocket('ws://h/a'); } other() { this.peer.send('x'); } }\n",
        )
        self.assertEqual([(m, p) for _, m, p, _, _ in found.calls], [('CONNECT', '/a')])

    def test_a_websocket_bound_to_another_library_is_not_read(self):
        found = Channels.of("import WebSocket from 'reconnecting-websocket';\nnew WebSocket('ws://h/a');\n")
        self.assertEqual(found.calls, [])


class WebSocketServerTest(unittest.TestCase):
    def test_server_paths(self):
        found = Channels.of(
            "const { WebSocketServer } = require('ws');\n"
            "const WebSocket = require('ws');\n"
            "const PATH = '/events';\n"
            'function attach(server) {\n'
            '  new WebSocketServer({ server, path: PATH });\n'
            "  new WebSocket.Server({ port: 8080, path: '/admin/ws' });\n"
            '  new WebSocketServer({ port: 8081 });\n'
            '  new WebSocketServer({ noServer: true });\n'
            "  new WebSocket.WebSocketServer({ port: 8082, path: '/feed' });\n"
            '}\n',
        )
        methods = ['CONNECT', 'SEND']
        self.assertEqual(
            found.routes,
            [
                (WS, methods, '/events', 'src/a.js', 5),
                (WS, methods, '/admin/ws', 'src/a.js', 6),
                (WS, methods, '/', 'src/a.js', 7),  # without a path, a server takes the root
                (WS, methods, '/feed', 'src/a.js', 9),
            ],
        )
        self.assertEqual(found.extraction.routes[0].framework, 'ws')

    def test_a_server_class_of_another_library_is_not_a_websocket_server(self):
        found = Channels.of("const { Server } = require('http');\nnew Server({ path: '/x' });\n")
        self.assertEqual(found.routes, [])


if __name__ == '__main__':
    unittest.main()
