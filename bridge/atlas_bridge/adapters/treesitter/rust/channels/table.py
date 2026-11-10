"""The library entry points that send to or receive on a channel other than HTTP, as one table."""

from typing import NamedTuple

from .....core.http import Protocol


class EntryPoint(NamedTuple):
    """One documented library call: `std::net::UdpSocket::send_to(&self, buf, addr)` sends UDP to `addr`.

    modules: the library modules that export `type` with this API. instance: called on a value of the type
    (`socket.send_to(..)`), else on the type (`TcpStream::connect(..)`). argument: which argument (after `self`)
    is the address. then: methods one of which must follow: on what a receiver returns (a UDP socket only receives
    on its bound address when it reads from it), or on the value an instance call is made on (a connected UDP socket
    only sends when it sends; `connect` alone, as when finding the local address, sends nothing). unless: calls
    that, given what it returns, make it carry another protocol (a listener handed to an HTTP server serves HTTP,
    found by its own routes). shape: how the argument names the channel, a socket address (ADDRESS: the port is the
    channel) or a topic name (NAME), or a slice of names (NAMES)."""

    modules: tuple[str, ...]
    type: str
    callee: str
    role: str
    protocol: str
    argument: int
    instance: bool = False
    then: frozenset[str] = frozenset()
    unless: frozenset[str] = frozenset()
    shape: str = 'address'

    def accepts(self, path: str) -> bool:
        """Whether a type's full path ('std::net::UdpSocket') is this entry point's type."""
        return any(path == f'{m}::{self.type}' for m in self.modules)


SEND, RECEIVE = 'send', 'receive'
KEY, KEYS = 'key', 'keys'  # EntryPoint.shape: a Redis key or channel (any text but blanks: 'jobs:pending'), or several
# redis: the connection types the command traits are used on, and the commands that name a key or channel first
REDIS_CONNECTIONS = (
    (('redis',), 'Client'),
    (('redis',), 'Connection'),
    (('redis::aio',), 'Connection'),
    (('redis::aio',), 'MultiplexedConnection'),
    (('redis::aio',), 'ConnectionManager'),
    (('redis::cluster',), 'ClusterConnection'),
    (('redis::cluster_async',), 'ClusterConnection'),
)
REDIS_COMMANDS = (
    ('publish', SEND),
    *((push, SEND) for push in ('lpush', 'rpush', 'lpush_exists', 'rpush_exists', 'xadd', 'xadd_maxlen')),
    *((pop, RECEIVE) for pop in ('blpop', 'brpop', 'lpop', 'rpop', 'blmove', 'lmove', 'brpoplpush', 'rpoplpush')),
)
REDIS_MULTIPLEXED = (
    'get_multiplexed_async_connection',
    'get_multiplexed_tokio_connection',
    'get_multiplexed_async_std_connection',
    'get_multiplexed_async_connection_with_config',
)


class EntryPoints:
    """Lookup of ENTRIES by the name called and whether it is called on a value."""

    SEND = SEND
    RECEIVE = RECEIVE
    ADDRESS, NAME, NAMES = 'address', 'name', 'names'  # EntryPoint.shape
    KEY, KEYS = KEY, KEYS
    SOCKETS = ('std::net', 'tokio::net', 'async_std::net')  # the same socket API in std, tokio and async-std
    # UdpSocket reads in std, tokio and async-std: blocking/async, try_ (non-blocking) and poll_ (manual futures).
    UDP_READS = frozenset({
        'recv', 'recv_from', 'peek', 'peek_from', 'recv_buf', 'recv_buf_from',
        'try_recv', 'try_recv_from', 'try_recv_buf', 'try_recv_buf_from', 'try_peek_from',
        'poll_recv', 'poll_recv_from', 'poll_peek_from',
    })  # fmt: skip
    UDP_SENDS = frozenset({'send', 'try_send', 'poll_send'})  # a connected UdpSocket's sends to its peer
    # Servers that take a bound TCP listener: axum::serve, axum_server::from_tcp, hyper's Server::from_tcp,
    # actix-web HttpServer::listen, tonic's serve_with_incoming, warp's run_incoming.
    SERVES = frozenset({'serve', 'from_tcp', 'listen', 'serve_with_incoming', 'run_incoming'})
    # rdkafka: the records a producer sends (re-exported in rdkafka::producer) and the consumers that subscribe.
    RECORDS = ('rdkafka::producer', 'rdkafka::producer::base_producer', 'rdkafka::producer::future_producer')
    CONSUMERS = ('rdkafka::consumer', 'rdkafka::consumer::stream_consumer', 'rdkafka::consumer::base_consumer')
    ENTRIES = (
        EntryPoint(SOCKETS, 'TcpStream', 'connect', SEND, Protocol.TCP, 0),
        EntryPoint(('std::net',), 'TcpStream', 'connect_timeout', SEND, Protocol.TCP, 0),
        EntryPoint(SOCKETS, 'TcpListener', 'bind', RECEIVE, Protocol.TCP, 0, unless=SERVES),
        EntryPoint(SOCKETS, 'UdpSocket', 'send_to', SEND, Protocol.UDP, 1, instance=True),
        EntryPoint(SOCKETS, 'UdpSocket', 'connect', SEND, Protocol.UDP, 0, instance=True, then=UDP_SENDS),
        EntryPoint(SOCKETS, 'UdpSocket', 'bind', RECEIVE, Protocol.UDP, 0, then=UDP_READS),
        # rdkafka: BaseRecord::to(topic) / FutureRecord::to(topic) is a message for that topic; a consumer's
        # subscribe(&[topics]) (the Consumer trait) receives on each
        EntryPoint(RECORDS, 'BaseRecord', 'to', SEND, Protocol.KAFKA, 0, shape=NAME),
        EntryPoint(RECORDS, 'FutureRecord', 'to', SEND, Protocol.KAFKA, 0, shape=NAME),
        EntryPoint(CONSUMERS, 'StreamConsumer', 'subscribe', RECEIVE, Protocol.KAFKA, 0, instance=True, shape=NAMES),
        EntryPoint(CONSUMERS, 'BaseConsumer', 'subscribe', RECEIVE, Protocol.KAFKA, 0, instance=True, shape=NAMES),
        # redis: the commands of the Commands / AsyncCommands traits on every connection type, the key or channel
        # first: publish(channel, msg); lpush / rpush(key, value) and xadd(key, id, items) append to a list or
        # stream; blpop / brpop(key, timeout), lpop / rpop(key, count) and xread(keys, ids) take from them;
        # PubSub::subscribe(channel) receives
        *(
            EntryPoint(modules, kind, command, role, Protocol.REDIS, 0, instance=True, shape=KEY)
            for modules, kind in REDIS_CONNECTIONS
            for command, role in REDIS_COMMANDS
        ),
        *(
            EntryPoint(modules, kind, 'xread', RECEIVE, Protocol.REDIS, 0, instance=True, shape=KEYS)
            for modules, kind in REDIS_CONNECTIONS
        ),
        *(
            EntryPoint((module,), 'PubSub', 'subscribe', RECEIVE, Protocol.REDIS, 0, instance=True, shape=KEY)
            for module in ('redis', 'redis::aio')
        ),
    )
    # What a library call returns, for the types of values made by calls the crate does not define:
    # (type, associated fn or method) -> the full path of the type it returns.
    RETURNS = {
        ('redis::Client', 'open'): 'redis::Client',
        ('redis::Client', 'get_connection'): 'redis::Connection',
        ('redis::Client', 'get_async_connection'): 'redis::aio::Connection',
        **{('redis::Client', m): 'redis::aio::MultiplexedConnection' for m in REDIS_MULTIPLEXED},
        ('redis::Client', 'get_connection_manager'): 'redis::aio::ConnectionManager',
        ('redis::Client', 'get_async_pubsub'): 'redis::aio::PubSub',
        ('redis::Connection', 'as_pubsub'): 'redis::PubSub',
        ('redis::aio::ConnectionManager', 'new'): 'redis::aio::ConnectionManager',
    }

    def __init__(self, entries=ENTRIES):
        self._by_call = {}
        for e in entries:
            self._by_call.setdefault((e.callee, e.instance), []).append(e)

    def named(self, callee: str, instance: bool) -> list[EntryPoint]:
        return self._by_call.get((callee, instance), [])

    @staticmethod
    def match(entries, path: str) -> EntryPoint | None:
        return next((e for e in entries if e.accepts(path)), None)
