import unittest

from atlas_bridge.adapters.treesitter.javascript.channels.collector import ChannelCollector

from ..support import Repository
from .support import Channels


class ImportedValuesTest(unittest.TestCase):
    def test_a_parameter_property_defaults_to_an_imported_constant(self):
        found = Channels(
            {
                'src/config.ts': "const env = import.meta.env ?? {};\nexport const WS_URL = env.WS ?? 'ws://h:1/rt';\n",
                'src/socket.ts': (
                    "import { WS_URL } from './config.js';\n"
                    'export class Socket {\n'
                    '  private ws?: WebSocket;\n'
                    '  constructor(private user: string, private url: string = WS_URL) {}\n'
                    '  connect() { this.ws = new WebSocket(`${this.url}?user=${this.user}`); }\n'
                    '  emit(frame) { this.ws?.send(JSON.stringify(frame)); }\n'
                    '}\n'
                ),
                'src/main.ts': "import { Socket } from './socket';\nnew Socket('ann').connect();\n",
            }
        )
        self.assertEqual(
            [(m, p, f) for _, m, p, f, _ in found.calls],
            [('CONNECT', '/rt', 'src/socket.ts'), ('SEND', '/rt', 'src/socket.ts')],
        )

    def test_a_constructor_argument_built_by_an_imported_helper(self):
        found = Channels(
            {
                'src/config.ts': (
                    "export const config = { base: process.env.BASE ?? 'http://dispatch:80' };\n"
                    'export function feedUrl(): string {\n'
                    "  const url = new URL('/feeds/live', config.base);\n"
                    '  return url.toString();\n'
                    '}\n'
                ),
                'src/conn.ts': (
                    "import WebSocket from 'ws';\n"
                    'export class Conn {\n'
                    '  constructor(private readonly url: string) {}\n'
                    '  open() { const s = new WebSocket(this.url); this.socket = s; }\n'
                    "  ping() { this.socket.send('ping'); }\n"
                    '}\n'
                ),
                'src/index.ts': "import { feedUrl } from './config.js';\nimport { Conn } from './conn.js';\n"
                'const c = new Conn(feedUrl());\n',
            }
        )
        self.assertEqual(
            [(m, p) for _, m, p, _, _ in found.calls], [('CONNECT', '/feeds/live'), ('SEND', '/feeds/live')]
        )

    def test_a_method_parameter_filled_in_through_an_imported_instance(self):
        found = Channels(
            {
                'src/config.js': "const config = { feedPath: process.env.FEED_PATH || '/feed' };\n"
                'module.exports = config;\n',
                'src/hub.js': (
                    "const { WebSocketServer } = require('ws');\n"
                    'class Hub {\n'
                    '  attach(server, path) { this.wss = new WebSocketServer({ server, path }); }\n'
                    '}\n'
                    'module.exports = new Hub();\n'
                ),
                'src/index.js': "const config = require('./config');\nconst hub = require('./hub');\n"
                'hub.attach(server, config.feedPath);\n',
            }
        )
        self.assertEqual([(p, f, line) for _, _, p, f, line in found.routes], [('/feed', 'src/hub.js', 3)])

    def test_each_caller_of_a_wrapper_names_its_own_channel(self):
        found = Channels.of(
            "const { WebSocketServer } = require('ws');\n"
            'function attach(path) { return new WebSocketServer({ path }); }\n'
            "attach('/a');\nattach('/b');\n",
        )
        self.assertEqual([p for _, _, p, _, _ in found.routes], ['/a', '/b'])

    def test_a_part_the_callers_disagree_on_is_not_guessed(self):
        found = Channels.of(
            "import { Kafka } from 'kafkajs';\n"
            'const producer = new Kafka({}).producer();\n'
            'function emit(prefix, e) { return producer.send({ topic: `${prefix}.created`, messages: [e] }); }\n'
            "emit('orders', 1);\nemit('users', 2);\n",
        )
        self.assertEqual(found.calls, [])

    def test_trees_are_released_once_read(self):
        ws = Repository.workspace(
            [
                ('src/config.js', 'module.exports = { port: 7000 };\n'),
                ('src/a.js', "const net = require('net');\nconst c = require('./config');\nnet.connect(c.port);\n"),
            ]
        )
        self.assertEqual([str(c.path) for c in ChannelCollector(ws).collect().calls], ['/7000'])
        self.assertEqual([s.path for s in ws.sources if s.parsed], [])


if __name__ == '__main__':
    unittest.main()
