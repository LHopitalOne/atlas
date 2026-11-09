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


if __name__ == '__main__':
    unittest.main()
