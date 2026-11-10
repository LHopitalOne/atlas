"""The library entry points that send or receive on a channel other than HTTP, as one table.

Each Entry is one documented API of a library: where it is called (a constructor or function of the library, a
method in a file that imports the library, or a method of an object an earlier entry made), whether it sends or
receives, over which protocol, and which argument names the channel. The machinery around it (channels.matcher,
channels.reader) knows no library.
"""

from dataclasses import dataclass

from .....core.http import ANY, Protocol


class Role:
    SEND = 'send'
    RECEIVE = 'receive'
    MAKE = 'make'  # only makes an object later entries are called on


class Form:
    """Where an entry is called."""

    NEW = 'new'  # `new <library name>(...)`: a constructor the library exports
    CALL = 'call'  # `<library name>(...)`: a function the library exports
    METHOD = 'method'  # `x.<callee>(...)` in a file that imports the library
    ON_CALL = 'on_call'  # `x.<callee>(...)` on an object made by entry `on`
    ON_NEW = 'on_new'  # `new x.<Name>(...)` on an object made by entry `on`
    ON_MEMBER = 'on_member'  # `x.<name>` (no call) on an object made by entry `on`: a getter like `socket.broadcast`


class Reading:
    """How the channel argument's value becomes a channel path."""

    URL = 'url'  # a URL or path: its path ('ws://h:1/ws' -> '/ws')
    NAME = 'name'  # a topic, queue or redis channel: '/<name>'
    PORT = 'port'  # a port number: '/<port>'
    ORIGIN = 'origin'  # the channel of the object the call is made on
    SERVICE = 'service'  # a gRPC service: the constructor's last name ('/<Service>')
    RPC = 'rpc'  # a gRPC method of a client: '<origin channel>/<Method>'
    IMPLEMENTATION = 'implementation'  # gRPC addService(<pkg>.<Service>.service, {Method: impl}): one per method
    JOB = 'job'  # a job added to a queue: '<origin channel>/<job name>'
    JOBS = 'jobs'  # jobs added at once: '<origin channel>/<name>' for the `name` of each object of a list
    WORKER = (
        'worker'  # a queue's worker: '/<queue>/<job>' for each job name its processor dispatches on, else every job
    )
    PROCESSOR = 'processor'  # a class decorated as a queue's worker: the same, read from its `process` method
    ROOT = 'root'  # always '/': Socket.IO's main namespace, which a server serves without naming it
    EVENT = 'event'  # a Socket.IO event: '<origin namespace>:<event name>' ('/quiz:join', '/:chat message')


@dataclass(frozen=True)
class Arg:
    """Where a call names its channel: the argument at `index`, or the `key` of the options object there."""

    index: int = 0
    key: str = ''  # the property that holds it when the argument is an object literal
    many: str = ''  # a property that holds a list of channels
    default: str = ''  # the channel when the argument (or key) is left out
    every: bool = False  # every argument from `index` on names a channel
    # the index to read instead when the call has an argument there that is not a callback: dgram's
    # send(msg, offset, length, port[, address][, callback]) against send(msg, port[, address][, callback])
    long_index: int = -1
    unless: str = ''  # an option that means the channel is not given here (`noServer`)
    positional: bool = True  # the argument itself names the channel when it is not an options object


@dataclass(frozen=True)
class Entry:
    libraries: frozenset[str]  # the modules that provide it; GLOBAL for a browser global
    form: str
    callee: str  # the qualified name (`WebSocket.Server`), the method name, or ANY_NAME
    role: str
    protocol: str = ''
    reading: str = ''
    arg: Arg | None = None
    methods: tuple[str, ...] = (ANY,)  # the method a call sends, or the methods a route accepts
    on: str = ''  # ON_CALL / ON_NEW: the name of the object the receiver must be made by
    makes: str = ''  # the name of the object this call makes, for later entries
    nested: bool = False  # members of the object it makes are that object too (`proto.inventory.v1`)
    min_args: int = 0
    max_args: int = 99
    hands: bool = False  # the object it makes is its callback's first parameter, not what it returns

    def fits(self, count):
        return self.min_args <= count <= self.max_args


GLOBAL = ''
ANY_NAME = '*'
WS = frozenset({GLOBAL, 'ws', 'isomorphic-ws'})
WS_SERVER = frozenset({'ws', 'isomorphic-ws'})  # isomorphic-ws re-exports ws in Node
KAFKA = frozenset({'kafkajs'})
AMQP = frozenset({'amqplib', 'amqplib/callback_api'})
REDIS = frozenset({'ioredis', 'redis', '@redis/client'})
GRPC = frozenset({'@grpc/grpc-js', 'grpc'})
NET = frozenset({'net'})
DGRAM = frozenset({'dgram'})
BULLMQ = frozenset({'bullmq'})
NEST_BULLMQ = frozenset({'@nestjs/bullmq'})
SIO_CLIENT = frozenset({'socket.io-client'})
SIO_SERVER = frozenset({'socket.io'})
SIO = SIO_CLIENT | SIO_SERVER

SOCKET = 'websocket'  # the object `new WebSocket(url)` makes
PORT = Arg(0, key='port')
TOPIC = Arg(0, key='topic', positional=False)
TOPICS = Arg(0, key='topic', many='topics', positional=False)
# a `ws` server without a path takes every path; with `noServer` the code routes upgrades itself
SERVER_PATH = Arg(0, key='path', default='/', unless='noServer', positional=False)
CONNECT_SEND = ('CONNECT', 'SEND')
QUEUE = 'bullmq.queue'  # the object `new Queue(name)` makes, or a queue NestJS injects
SIO_SOCKET = 'socketio.socket'  # one connection to a namespace: a client's socket, or the server's end of it
SIO_MANAGER = 'socketio.manager'  # a client's connection manager, which opens sockets to namespaces
SIO_NAMESPACE = 'socketio.namespace'  # a server's namespace (the Server itself is the main one), or a broadcast on it
EMIT = ('EMIT',)
WS_ = Protocol.WEBSOCKET
MAIN = Arg(0, default='/')  # a Socket.IO namespace, the main one when none is given
SIO_NARROWS = ('to', 'in', 'except', 'timeout', 'compress')  # methods that return the same emitter, narrowed
SIO_GETTERS = ('broadcast', 'volatile', 'local')
# Socket.IO's own events, which no application emits: connection lifecycle and the Manager's reconnection events
SIO_RESERVED = frozenset(
    {
        'connect',
        'connection',
        'connect_error',
        'disconnect',
        'disconnecting',
        'error',
        'newListener',
        'removeListener',
        'reconnect',
        'reconnect_attempt',
        'reconnect_error',
        'reconnect_failed',
        'ping',
    }
)

ENTRIES = (
    # WebSocket (browser global, `ws`): the client opens a URL, then sends on it; a `ws` server listens on a path
    Entry(WS, Form.NEW, 'WebSocket', Role.SEND, Protocol.WEBSOCKET, Reading.URL, Arg(0), ('CONNECT',), makes=SOCKET),
    Entry(WS, Form.ON_CALL, 'send', Role.SEND, Protocol.WEBSOCKET, Reading.ORIGIN, methods=('SEND',), on=SOCKET),
    *(
        Entry(WS_SERVER, Form.NEW, name, Role.RECEIVE, Protocol.WEBSOCKET, Reading.URL, SERVER_PATH, CONNECT_SEND)
        for name in ('WebSocketServer', 'WebSocket.WebSocketServer', 'WebSocket.Server', 'Server')
    ),
    # kafkajs: producer.send({ topic, messages }), consumer.subscribe({ topic } | { topics: [...] })
    Entry(KAFKA, Form.METHOD, 'send', Role.SEND, Protocol.KAFKA, Reading.NAME, TOPIC),
    Entry(KAFKA, Form.METHOD, 'subscribe', Role.RECEIVE, Protocol.KAFKA, Reading.NAME, TOPICS),
    # amqplib: channel.sendToQueue(queue, ...), channel.publish(exchange, routingKey, content), channel.consume(queue);
    # channel.bindQueue(queue, exchange, pattern) receives what is published with that routing key
    Entry(AMQP, Form.METHOD, 'sendToQueue', Role.SEND, Protocol.AMQP, Reading.NAME, Arg(0), min_args=2),
    Entry(AMQP, Form.METHOD, 'publish', Role.SEND, Protocol.AMQP, Reading.NAME, Arg(1), min_args=3),
    Entry(AMQP, Form.METHOD, 'consume', Role.RECEIVE, Protocol.AMQP, Reading.NAME, Arg(0), min_args=2),
    Entry(AMQP, Form.METHOD, 'bindQueue', Role.RECEIVE, Protocol.AMQP, Reading.NAME, Arg(2), min_args=3),
    # ioredis / node-redis: publish(channel, message), subscribe(channel, ...)
    Entry(REDIS, Form.METHOD, 'publish', Role.SEND, Protocol.REDIS, Reading.NAME, Arg(0), min_args=2, max_args=2),
    Entry(REDIS, Form.METHOD, 'subscribe', Role.RECEIVE, Protocol.REDIS, Reading.NAME, Arg(0, every=True)),
    # @grpc/grpc-js + @grpc/proto-loader: new <pkg>.<Service>(address, credentials) from loadPackageDefinition,
    # client.<Method>(...); server.addService(<pkg>.<Service>.service, { <Method>: impl })
    Entry(GRPC, Form.CALL, 'loadPackageDefinition', Role.MAKE, makes='grpc.package', nested=True),
    Entry(GRPC, Form.ON_NEW, ANY_NAME, Role.MAKE, Protocol.GRPC, Reading.SERVICE, on='grpc.package', makes='grpc'),
    Entry(GRPC, Form.ON_CALL, ANY_NAME, Role.SEND, Protocol.GRPC, Reading.RPC, methods=('CALL',), on='grpc'),
    Entry(GRPC, Form.METHOD, 'addService', Role.RECEIVE, Protocol.GRPC, Reading.IMPLEMENTATION, Arg(0), ('CALL',)),
    # net: net.connect / net.createConnection({ port, host } | port, host); net.createServer(...).listen(port)
    Entry(NET, Form.CALL, 'connect', Role.SEND, Protocol.TCP, Reading.PORT, PORT),
    Entry(NET, Form.CALL, 'createConnection', Role.SEND, Protocol.TCP, Reading.PORT, PORT),
    Entry(NET, Form.NEW, 'Socket', Role.MAKE, makes='net.socket'),
    Entry(NET, Form.ON_CALL, 'connect', Role.SEND, Protocol.TCP, Reading.PORT, PORT, on='net.socket'),
    Entry(NET, Form.CALL, 'createServer', Role.MAKE, makes='net.server'),
    Entry(NET, Form.ON_CALL, 'listen', Role.RECEIVE, Protocol.TCP, Reading.PORT, PORT, on='net.server'),
    # dgram: dgram.createSocket(...), socket.send(msg, port, host) / send(msg, offset, length, port, host),
    # socket.bind(port); a port of 0 (any free port) is no channel
    Entry(DGRAM, Form.CALL, 'createSocket', Role.MAKE, makes='dgram.socket'),
    Entry(DGRAM, Form.ON_CALL, 'send', Role.SEND, Protocol.UDP, Reading.PORT, Arg(1, long_index=3), on='dgram.socket'),
    Entry(DGRAM, Form.ON_CALL, 'bind', Role.RECEIVE, Protocol.UDP, Reading.PORT, PORT, on='dgram.socket'),
    # bullmq: new Queue(name), queue.add(jobName, data), queue.addBulk([{ name, data }]); new Worker(name, processor)
    # runs the jobs of the queue. @nestjs/bullmq: @InjectQueue(name) injects a queue, @Processor(name) on a WorkerHost
    # class makes its process(job) the worker
    Entry(BULLMQ, Form.NEW, 'Queue', Role.MAKE, Protocol.TASK, Reading.NAME, Arg(0), makes=QUEUE),
    Entry(NEST_BULLMQ, Form.CALL, 'InjectQueue', Role.MAKE, Protocol.TASK, Reading.NAME, Arg(0), makes=QUEUE),
    Entry(BULLMQ, Form.ON_CALL, 'add', Role.SEND, Protocol.TASK, Reading.JOB, Arg(0), on=QUEUE, min_args=1),
    Entry(BULLMQ, Form.ON_CALL, 'addBulk', Role.SEND, Protocol.TASK, Reading.JOBS, Arg(0, key='name'), on=QUEUE),
    Entry(BULLMQ, Form.NEW, 'Worker', Role.RECEIVE, Protocol.TASK, Reading.WORKER, Arg(0)),
    Entry(NEST_BULLMQ, Form.CALL, 'Processor', Role.RECEIVE, Protocol.TASK, Reading.PROCESSOR, Arg(0, key='name')),
    # Socket.IO: a client connects to the namespace its URL names (`io('http://h/chat')`, `manager.socket('/chat')`);
    # a server's namespaces are the main one ('/') and `io.of(name)`; `nsp.on('connection', (socket) => ...)` hands
    # each connection to its callback. Both ends emit(event, ...) and receive with on/once(event, handler); to(room),
    # in, except, timeout, compress and the getters broadcast, volatile, local narrow an emit to the same namespace.
    *(
        Entry(SIO_CLIENT, Form.CALL, name, Role.MAKE, Protocol.WEBSOCKET, Reading.URL, MAIN, makes=SIO_SOCKET)
        for name in ('io', 'connect', 'io.connect')
    ),
    Entry(SIO_CLIENT, Form.NEW, 'Manager', Role.MAKE, makes=SIO_MANAGER),
    Entry(SIO_CLIENT, Form.ON_CALL, 'socket', Role.MAKE, WS_, Reading.NAME, MAIN, on=SIO_MANAGER, makes=SIO_SOCKET),
    Entry(SIO_SERVER, Form.NEW, 'Server', Role.MAKE, WS_, Reading.ROOT, makes=SIO_NAMESPACE),
    Entry(SIO_SERVER, Form.ON_CALL, 'of', Role.MAKE, WS_, Reading.NAME, Arg(0), on=SIO_NAMESPACE, makes=SIO_NAMESPACE),
    Entry(
        SIO_SERVER, Form.ON_CALL, 'on', Role.MAKE, WS_, Reading.ORIGIN, on=SIO_NAMESPACE, makes=SIO_SOCKET, hands=True
    ),
    *(
        Entry(SIO, form, name, Role.MAKE, WS_, Reading.ORIGIN, on=made, makes=made)
        for made in (SIO_SOCKET, SIO_NAMESPACE)
        for form, names in ((Form.ON_CALL, SIO_NARROWS), (Form.ON_MEMBER, SIO_GETTERS))
        for name in names
    ),
    *(
        Entry(SIO, Form.ON_CALL, name, Role.SEND, WS_, Reading.EVENT, Arg(0), EMIT, on=made, min_args=1)
        for made in (SIO_SOCKET, SIO_NAMESPACE)
        for name in ('emit', 'emitWithAck')
    ),
    *(
        Entry(SIO, Form.ON_CALL, name, Role.RECEIVE, WS_, Reading.EVENT, Arg(0), EMIT, on=SIO_SOCKET, min_args=2)
        for name in ('on', 'once')
    ),
)

# what a module's default export is called in ENTRIES (`import WebSocket from 'ws'`); '' for a namespace of functions
DEFAULT_EXPORTS = {'ws': 'WebSocket', 'isomorphic-ws': 'WebSocket', 'socket.io-client': 'io'}
# methods every gRPC client has, which are not RPCs of its service
CLIENT_METHODS = frozenset(
    {
        'close',
        'getChannel',
        'waitForReady',
        'makeUnaryRequest',
        'makeClientStreamRequest',
        'makeServerStreamRequest',
        'makeBidiStreamRequest',
    }
)
