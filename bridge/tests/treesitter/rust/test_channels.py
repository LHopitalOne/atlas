import unittest

from atlas_bridge.core.http import Extraction, Protocol
from atlas_bridge.usecases.link import LinkFinder

from .support import RustRepo

SETTINGS = """
use std::env;

pub struct Settings {
    pub stream_addr: String,
    pub gauge_addr: String,
}

fn var_or(name: &str, fallback: &str) -> String {
    env::var(name).unwrap_or_else(|_| fallback.to_string())
}

impl Settings {
    pub fn load() -> Self {
        let host = var_or("SINK_HOST", "127.0.0.1");
        let port = var_or("SINK_PORT", "7001");
        let gauge_port = env::var("GAUGE_PORT").unwrap_or("7002".to_string());
        Settings {
            stream_addr: format!("{host}:{port}"),
            gauge_addr: format!("{}:{}", &host, gauge_port.as_str()),
        }
    }
}
"""

STREAM = """
use std::io;
use std::net::TcpStream;

pub struct Stream {
    addr: String,
    inner: TcpStream,
}

impl Stream {
    pub fn open(addr: &str) -> io::Result<Self> {
        let inner = TcpStream::connect(addr)?;
        Ok(Stream { addr: addr.to_string(), inner })
    }

    pub fn reopen(&mut self) -> io::Result<()> {
        *self = Stream::open(&self.addr)?;
        Ok(())
    }
}
"""

GAUGES = """
use std::net::UdpSocket;
use std::sync::Arc;

pub struct Gauges {
    socket: Arc<UdpSocket>,
    to: String,
}

impl Gauges {
    pub fn new(to: &str) -> std::io::Result<Self> {
        let socket = UdpSocket::bind("0.0.0.0:0")?;
        Ok(Gauges { socket: Arc::new(socket), to: to.to_string() })
    }

    pub fn emit(&self, line: &str) {
        let _ = self.socket.send_to(line.as_bytes(), &self.to);
    }
}
"""

MAIN = """
mod gauges;
mod settings;
mod stream;

use gauges::Gauges;
use settings::Settings;
use stream::Stream;

fn main() {
    let settings = Settings::load();
    let mut out = Stream::open(&settings.stream_addr).unwrap();
    let gauges = Gauges::new(&settings.gauge_addr).unwrap();
    gauges.emit("up:1|c");
    out.reopen().unwrap();
}
"""

SENDER = {'src/settings.rs': SETTINGS, 'src/stream.rs': STREAM, 'src/gauges.rs': GAUGES, 'src/main.rs': MAIN}

RECEIVER = """
use std::env;
use tokio::net::{TcpListener, UdpSocket};

const TCP_PORT: u16 = 7001;

fn udp_port() -> u16 {
    env::var("UDP_PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(7002)
}

async fn serve() -> std::io::Result<()> {
    let listener = TcpListener::bind(format!("0.0.0.0:{}", TCP_PORT)).await?;
    let socket = UdpSocket::bind(("0.0.0.0", udp_port())).await?;
    let mut buf = [0u8; 512];
    let (n, from) = socket.recv_from(&mut buf).await?;
    let reply = UdpSocket::bind("0.0.0.0:7003").await?;
    reply.send_to(&buf[..n], from).await?;
    let _ = listener.accept().await?;
    Ok(())
}
"""


def channels(found):
    return sorted((x.protocol, str(x.path), x.file, x.line) for x in found if x.protocol != Protocol.HTTP)


class ChannelCallTest(unittest.TestCase):
    def test_addresses_followed_through_wrappers_fields_and_env_defaults(self):
        calls = RustRepo(SENDER).extract().calls
        self.assertEqual(
            channels(calls),
            [('tcp', '/7001', 'src/stream.rs', 12), ('udp', '/7002', 'src/gauges.rs', 17)],
        )
        tcp = next(c for c in calls if c.protocol == Protocol.TCP)
        self.assertEqual((tcp.function, tcp.method, tcp.test), ('Stream::open', 'ANY', False))
        self.assertTrue({'addr', 'src/stream.rs'} <= tcp.hints)

    def test_literal_tuple_and_full_path_addresses(self):
        calls = (
            RustRepo(
                """
use tokio::net::UdpSocket;

const PORT: u16 = 6100;

async fn send(sock: &UdpSocket, buf: &[u8]) {
    std::net::TcpStream::connect("10.0.0.1:6000").unwrap();
    tokio::net::TcpStream::connect(("db", PORT)).await.unwrap();
    sock.send_to(buf, "[::1]:6200").await.unwrap();
    sock.connect(format!("{}:{}", "relay", 6300)).await.unwrap();
    sock.send(buf).await.unwrap();
}
"""
            )
            .extract()
            .calls
        )
        self.assertEqual(
            [(c, p) for c, p, _, _ in channels(calls)],
            [('tcp', '/6000'), ('tcp', '/6100'), ('udp', '/6200'), ('udp', '/6300')],
        )

    def test_methods_on_typed_values_and_struct_fields_in_format_arguments(self):
        calls = (
            RustRepo(
                """
use std::net::{SocketAddr, TcpStream, UdpSocket};

const DEFAULT_PORT: u16 = 6500;

pub struct Peer {
    host: String,
    port: u16,
}

impl Peer {
    pub fn new() -> Self {
        Peer { host: "peer".to_string(), port: DEFAULT_PORT }
    }

    pub fn addr(&self) -> String {
        format!("{}:{}", self.host, self.port.to_string())
    }

    pub fn dial(&self) {
        TcpStream::connect(format!("{}:{}", &self.host, self.port)).unwrap();
    }
}

fn run(sock: UdpSocket) {
    let peer = Peer::new();
    sock.send_to(b"x", peer.addr()).unwrap();
    let to: SocketAddr = "10.1.1.1:6600".parse().unwrap();
    sock.send_to(b"x", to).unwrap();
}
"""
            )
            .extract()
            .calls
        )
        self.assertEqual(
            sorted((c.protocol, str(c.path), c.function) for c in calls),
            [('tcp', '/6500', 'Peer::dial'), ('udp', '/6500', 'run'), ('udp', '/6600', 'run')],
        )

    def test_unknown_ports_and_other_types_are_not_channels(self):
        calls = (
            RustRepo(
                """
use std::env;
use std::net::{TcpStream, UdpSocket};

struct Pool;
impl Pool {
    fn connect(addr: &str) -> Pool { Pool }
}

fn send(sock: UdpSocket, peers: Peers, addr: String) {
    TcpStream::connect(env::var("TARGET").unwrap()).unwrap();
    TcpStream::connect(addr).unwrap();
    sock.send_to(b"x", "localhost:0").unwrap();
    Pool::connect("db:5432");
    peers.send_to(b"x", "peer:7000");
}
"""
            )
            .extract()
            .calls
        )
        self.assertEqual(channels(calls), [])

    def test_integer_literals_in_any_base_and_a_connect_that_never_sends(self):
        calls = (
            RustRepo(
                """
use std::net::UdpSocket;

const HEX: u16 = 0x1F90;

pub struct Probe {
    sock: UdpSocket,
}

impl Probe {
    fn open(&self) {
        self.sock.connect(("relay", 8_125u16)).unwrap();
    }

    fn flush(&self, buf: &[u8]) {
        self.sock.send(buf).unwrap();
    }
}

fn local_ip() -> std::net::IpAddr {
    let sock = UdpSocket::bind("0.0.0.0:0").unwrap();
    sock.connect("8.8.8.8:80").unwrap();
    sock.local_addr().unwrap().ip()
}

fn emit(sock: &UdpSocket) {
    sock.send_to(b"x", ("peer", HEX)).unwrap();
}
"""
            )
            .extract()
            .calls
        )
        self.assertEqual([(c, p) for c, p, _, _ in channels(calls)], [('udp', '/8080'), ('udp', '/8125')])

    def test_calls_in_tests_are_marked(self):
        calls = (
            RustRepo(
                """
#[cfg(test)]
mod tests {
    use std::net::TcpStream;

    #[test]
    fn talks() {
        TcpStream::connect("127.0.0.1:7400").unwrap();
    }
}
"""
            )
            .extract()
            .calls
        )
        self.assertEqual([(str(c.path), c.test) for c in calls], [('/7400', True)])


class ChannelRouteTest(unittest.TestCase):
    def test_listeners_and_read_udp_sockets_receive(self):
        routes = RustRepo({'src/server.rs': RECEIVER}).extract().routes
        self.assertEqual(
            channels(routes),
            [('tcp', '/7001', 'src/server.rs', 12), ('udp', '/7002', 'src/server.rs', 13)],
        )
        self.assertEqual({r.handler for r in routes}, {'serve'})

    def test_a_socket_read_through_a_struct_field_receives(self):
        routes = (
            RustRepo(
                """
use std::net::UdpSocket;

pub struct Listener {
    sock: UdpSocket,
}

impl Listener {
    pub fn new() -> std::io::Result<Self> {
        let sock = UdpSocket::bind("0.0.0.0:7500")?;
        Ok(Self { sock })
    }

    pub fn next(&self, buf: &mut [u8]) -> std::io::Result<usize> {
        self.sock.recv(buf)
    }
}
"""
            )
            .extract()
            .routes
        )
        self.assertEqual(channels(routes), [('udp', '/7500', 'src/client.rs', 10)])

    def test_sending_sockets_and_test_code_do_not_receive(self):
        routes = (
            RustRepo(
                """
use std::net::{TcpListener, UdpSocket};

fn send() {
    let sock = UdpSocket::bind("0.0.0.0:7600").unwrap();
    sock.send_to(b"x", "peer:7601").unwrap();
}

#[test]
fn listens() {
    TcpListener::bind("127.0.0.1:7602").unwrap();
}
"""
            )
            .extract()
            .routes
        )
        self.assertEqual(channels(routes), [])

    def test_listeners_handed_to_a_server_serve_its_protocol(self):
        routes = (
            RustRepo(
                """
use tokio::net::TcpListener;

async fn main() {
    let app = Router::new().route("/health", get(health));
    let listener = TcpListener::bind("0.0.0.0:7700").await.expect("bind");
    axum::serve(listener, app).await.unwrap();
}

async fn grpc() {
    let incoming = TcpListenerStream::new(TcpListener::bind("0.0.0.0:7701").await?);
    let raw = TcpListener::bind("0.0.0.0:7702").await?;
    Server::builder().serve_with_incoming(TcpListenerStream::new(raw)).await?;
}
"""
            )
            .extract()
            .routes
        )
        self.assertEqual(channels(routes), [('tcp', '/7701', 'src/client.rs', 11)])
        self.assertEqual([str(r.path) for r in routes if r.protocol == Protocol.HTTP], ['/health'])


class ChannelLinkTest(unittest.TestCase):
    def test_a_sender_links_to_the_receiver_on_its_port(self):
        sent = RustRepo(SENDER, repo='agent').extract()
        served = RustRepo({'src/server.rs': RECEIVER}, repo='sink').extract()
        links = LinkFinder(['agent', 'sink']).find(Extraction(served.routes, sent.calls))
        found = sorted((lk.call.protocol, str(lk.route.path), lk.target) for lk in links if lk.route)
        self.assertEqual(found, [('tcp', '/7001', 'sink'), ('udp', '/7002', 'sink')])
