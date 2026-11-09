"""The library entry points that send to or receive on a channel other than HTTP, as one table."""

from typing import NamedTuple

from .....core.http import Protocol


class EntryPoint(NamedTuple):
    """One documented library call: `std::net::UdpSocket::send_to(&self, buf, addr)` sends UDP to `addr`.

    modules: the library modules that export `type` with this API. instance: called on a value of the type
    (`socket.send_to(..)`), else on the type (`TcpStream::connect(..)`). argument: which argument (after `self`)
    is the address. then: for a receiver, the methods one of which must be called on what it returns (a UDP
    socket only receives on its bound address when it reads from it). unless: calls that, given what it returns,
    make it carry another protocol (a listener handed to an HTTP server serves HTTP, found by its own routes)."""

    modules: tuple[str, ...]
    type: str
    callee: str
    role: str
    protocol: str
    argument: int
    instance: bool = False
    then: frozenset[str] = frozenset()
    unless: frozenset[str] = frozenset()

    def accepts(self, path: str) -> bool:
        """Whether a type's full path ('std::net::UdpSocket') is this entry point's type."""
        return any(path == f'{m}::{self.type}' for m in self.modules)


class EntryPoints:
    """Lookup of ENTRIES by the name called and whether it is called on a value."""

    SEND = 'send'
    RECEIVE = 'receive'
    SOCKETS = ('std::net', 'tokio::net', 'async_std::net')  # the same socket API in std, tokio and async-std
    UDP_READS = frozenset({'recv', 'recv_from', 'peek_from', 'recv_buf', 'recv_buf_from'})
    # Servers that take a bound TCP listener: axum::serve, axum_server::from_tcp, hyper's Server::from_tcp,
    # actix-web HttpServer::listen, tonic's serve_with_incoming, warp's run_incoming.
    SERVES = frozenset({'serve', 'from_tcp', 'listen', 'serve_with_incoming', 'run_incoming'})
    ENTRIES = (
        EntryPoint(SOCKETS, 'TcpStream', 'connect', SEND, Protocol.TCP, 0),
        EntryPoint(('std::net',), 'TcpStream', 'connect_timeout', SEND, Protocol.TCP, 0),
        EntryPoint(SOCKETS, 'TcpListener', 'bind', RECEIVE, Protocol.TCP, 0, unless=SERVES),
        EntryPoint(SOCKETS, 'UdpSocket', 'send_to', SEND, Protocol.UDP, 1, instance=True),
        EntryPoint(SOCKETS, 'UdpSocket', 'connect', SEND, Protocol.UDP, 0, instance=True),
        EntryPoint(SOCKETS, 'UdpSocket', 'bind', RECEIVE, Protocol.UDP, 0, then=UDP_READS),
    )

    def __init__(self, entries=ENTRIES):
        self._by_call = {}
        for e in entries:
            self._by_call.setdefault((e.callee, e.instance), []).append(e)

    def named(self, callee: str, instance: bool) -> list[EntryPoint]:
        return self._by_call.get((callee, instance), [])

    @staticmethod
    def match(entries, path: str) -> EntryPoint | None:
        return next((e for e in entries if e.accepts(path)), None)
