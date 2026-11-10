import unittest

from atlas_bridge.core.http import Protocol

from .support import Channels

WS = Protocol.WEBSOCKET


class SocketIoClientTest(unittest.TestCase):
    def test_emit_and_on_in_the_namespace_of_the_url(self):
        found = Channels.of(
            "import { io } from 'socket.io-client';\n"
            "const socket = io('http://localhost:4000/chat');\n"
            "socket.emit('chat message', 'hi');\n"
            "socket.volatile.emit('typing');\n"
            "socket.timeout(500).emit('ping me');\n"
            "socket.on('chat message', (m) => {});\n"
            "socket.once('connect', () => {});\n"  # Socket.IO's own event
            "socket.on('disconnect', () => {});\n",
            path='src/a.ts',
        )
        self.assertEqual(
            [(p, m, path, line) for p, m, path, _, line in found.calls],
            [(WS, 'EMIT', '/chat:chat message', 3), (WS, 'EMIT', '/chat:typing', 4), (WS, 'EMIT', '/chat:ping me', 5)],
        )
        self.assertEqual([(path, line) for _, _, path, _, line in found.routes], [('/chat:chat message', 6)])

    def test_main_namespace_when_none_is_given(self):
        found = Channels.of(
            "import io from 'socket.io-client';\n"
            'const a = io();\n'
            "a.emit('hello');\n"
            "const b = io.connect('http://localhost:4000');\n"
            "b.emit('bye');\n",
        )
        self.assertEqual([path for _, _, path, _, _ in found.calls], ['/:hello', '/:bye'])

    def test_wrapper_class_with_event_constants_and_an_unknown_namespace(self):
        found = Channels(
            {
                'src/events.ts': "export const NS = '/game';\nexport const Events = { MOVE: 'move' } as const;\n",
                'src/client.ts': "import { io, type Socket } from 'socket.io-client';\n"
                "import { NS, Events } from './events.js';\n"
                'export class GameClient {\n'
                '  private readonly socket: Socket;\n'
                '  constructor(url: string) { this.socket = io(`${url}${NS}`); }\n'
                '  move(x: number) { this.send(Events.MOVE, { x }); }\n'
                '  private send(event: string, payload: object) { this.socket.emit(event, payload); }\n'
                '}\n'
                "export function hello(base: string) { io(base).emit('hello'); }\n",  # the namespace is not known
            }
        )
        self.assertEqual([(path, f, line) for _, _, path, f, line in found.calls], [('/game:move', 'src/client.ts', 7)])

    def test_manager_socket(self):
        found = Channels.of(
            "import { Manager } from 'socket.io-client';\n"
            "const manager = new Manager('http://localhost:4000');\n"
            "const admin = manager.socket('/admin');\n"
            "admin.emit('kick', 1);\n",
        )
        self.assertEqual([path for _, _, path, _, _ in found.calls], ['/admin:kick'])

    def test_emit_without_socket_io_is_no_channel(self):
        found = Channels.of(
            "import { EventEmitter } from 'node:events';\nconst bus = new EventEmitter();\n"
            "bus.emit('join', 1);\nbus.on('join', () => {});\n"
        )
        self.assertEqual((found.calls, found.routes), ([], []))


class SocketIoServerTest(unittest.TestCase):
    def test_connection_sockets_and_broadcasts_of_namespaces(self):
        found = Channels.of(
            "import { Server } from 'socket.io';\n"
            'const io = new Server(3000);\n'
            "io.on('connection', (socket) => {\n"
            "  socket.on('chat message', (m) => io.emit('chat message', m));\n"
            "  socket.broadcast.emit('joined');\n"
            "  socket.on('disconnect', () => {});\n"
            '});\n'
            "const admin = io.of('/admin');\n"
            'admin.on(\'connection\', socket => { socket.on("kick", () => {}); });\n'
            "admin.to('room').emit('kicked');\n",
            path='src/a.ts',
        )
        self.assertEqual(
            [(path, line) for _, _, path, _, line in found.routes], [('/:chat message', 4), ('/admin:kick', 9)]
        )
        self.assertEqual(
            [(path, line) for _, _, path, _, line in found.calls],
            [('/:chat message', 4), ('/:joined', 5), ('/admin:kicked', 10)],
        )

    def test_namespace_passed_to_another_file(self):
        found = Channels(
            {
                'src/server.ts': "import { Server } from 'socket.io';\n"
                "import { register } from './ns.js';\n"
                'const io = new Server(3000);\n'
                'register(io);\n',
                'src/ns.ts': "import type { Server, Namespace } from 'socket.io';\n"
                "import { Room } from './room.js';\n"
                'export function register(io: Server) {\n'
                "  const nsp = io.of('/quiz');\n"
                "  nsp.on('connection', (socket) => { socket.on('answer', () => new Room(nsp).ask()); });\n"
                '}\n',
                'src/room.ts': "import type { Namespace } from 'socket.io';\n"
                'export class Room {\n'
                '  constructor(private readonly nsp: Namespace) {}\n'
                "  ask() { this.nsp.to('r1').emit('question', {}); }\n"
                '}\n',
            }
        )
        self.assertEqual([(path, f) for _, _, path, f, _ in found.routes], [('/quiz:answer', 'src/ns.ts')])
        self.assertEqual([(path, f) for _, _, path, f, _ in found.calls], [('/quiz:question', 'src/room.ts')])


if __name__ == '__main__':
    unittest.main()
