import unittest

from atlas_bridge.core.http import ANY, Protocol

from .support import Channels

TCP, UDP = Protocol.TCP, Protocol.UDP


class NetTest(unittest.TestCase):
    def test_connections_and_servers(self):
        found = Channels.of(
            "const net = require('node:net');\n"
            'const PORT = Number(process.env.INGEST_PORT || 7400);\n'
            'net.connect({ port: PORT, host: "collector" });\n'
            "net.createConnection(7401, 'collector');\n"
            'net.createServer((socket) => socket.pipe(socket)).listen(PORT);\n'
            'const server = net.createServer(handle);\n'
            "server.listen({ port: 7402, host: '0.0.0.0' });\n"
            'const sock = new net.Socket();\n'
            "sock.connect(7403, 'collector');\n"
            "sock.connect('/tmp/app.sock');\n",  # an IPC path, not a port
        )
        self.assertEqual(
            [(p, m, path) for p, m, path, _, _ in found.calls],
            [(TCP, ANY, '/7400'), (TCP, ANY, '/7401'), (TCP, ANY, '/7403')],
        )
        self.assertEqual(
            [(p, path, line) for p, _, path, _, line in found.routes], [(TCP, '/7400', 5), (TCP, '/7402', 7)]
        )

    def test_an_http_server_is_not_a_tcp_channel(self):
        found = Channels.of(
            "import http from 'node:http';\nimport { createServer } from 'net';\n"
            'http.createServer(app).listen(8080);\n'
            'createServer(h).listen(9090);\n',
        )
        self.assertEqual([(p, path) for p, _, path, _, _ in found.routes], [(TCP, '/9090')])


class DgramTest(unittest.TestCase):
    def test_send_and_bind(self):
        found = Channels.of(
            "import dgram from 'dgram';\n"
            "const STATSD_PORT = parseInt(process.env.STATSD_PORT ?? '8125', 10);\n"
            "const socket = dgram.createSocket('udp4');\n"
            "socket.send('hits:1|c', STATSD_PORT, 'statsd');\n"
            "socket.send(buf, 0, buf.length, 8126, 'statsd', () => {});\n"
            'const listener = dgram.createSocket({ type: "udp4" });\n'
            'listener.bind(8125);\n'
            'listener.bind({ port: 8127 });\n',
        )
        self.assertEqual([(p, path) for p, _, path, _, _ in found.calls], [(UDP, '/8125'), (UDP, '/8126')])
        self.assertEqual([(p, path) for p, _, path, _, _ in found.routes], [(UDP, '/8125'), (UDP, '/8127')])

    def test_offset_and_length_without_an_address_and_port_zero(self):
        found = Channels.of(
            "const dgram = require('node:dgram');\n"
            "const socket = dgram.createSocket('udp4');\n"
            'socket.send(buf, 0, buf.length, 8130);\n'  # send(msg, offset, length, port): not port 0
            "socket.send(buf, 8131, 'statsd', (err) => {});\n"  # send(msg, port, address, callback)
            'socket.bind(0);\n'  # any free port: no channel
            'socket.bind();\n',
        )
        self.assertEqual([path for _, _, path, _, _ in found.calls], ['/8130', '/8131'])
        self.assertEqual(found.routes, [])

    def test_port_from_an_env_helper_through_a_class_and_a_config_object(self):
        found = Channels(
            {
                'src/config.ts': 'function envInt(name: string, fallback: number): number {\n'
                '  const raw = process.env[name];\n'
                '  return raw ? Number.parseInt(raw, 10) : fallback;\n'
                '}\n'
                'const envStr = (name: string, def: string) => process.env[name] ?? def;\n'
                'export const config = {\n'
                "  metrics: { host: envStr('STATSD_HOST', 'statsd'), port: envInt('STATSD_PORT', 8125) },\n"
                "  other: envInt('OTHER', Number(process.env.X)),\n"
                '} as const;\n',
                'src/reporter.ts': "import dgram from 'node:dgram';\n"
                'export class Reporter {\n'
                "  private readonly socket = dgram.createSocket('udp4');\n"
                '  constructor(private readonly host: string, private readonly port: number) {}\n'
                "  hit(): void { this.socket.send('hits:1|c', this.port, this.host); }\n"
                '}\n',
                'src/main.ts': "import { config } from './config.js';\nimport { Reporter } from './reporter.js';\n"
                'new Reporter(config.metrics.host, config.metrics.port).hit();\n',
                'src/other.ts': "import dgram from 'node:dgram';\nimport { config } from './config.js';\n"
                "dgram.createSocket('udp4').send('x', config.other, 'h');\n",
            }
        )
        self.assertEqual([(path, f) for _, _, path, f, _ in found.calls], [('/8125', 'src/reporter.ts')])


if __name__ == '__main__':
    unittest.main()
