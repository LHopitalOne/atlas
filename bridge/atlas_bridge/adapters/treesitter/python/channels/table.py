"""The messaging and socket libraries the Python extractor knows: which objects they make and which calls send to or
receive on a channel. Every row restates a library's documented API; the machinery that reads them is shared."""

from typing import NamedTuple

from .....core.http import ANY, Protocol


class Role:
    SEND = 'send'  # a Call: the code sends on the channel
    RECEIVE = 'receive'  # a Route: the code receives on it


class Shape:
    """How the channel argument is written."""

    NAME = 'name'  # a topic, queue or channel name: 'orders.created'
    NAMES = 'names'  # a list or tuple of names, or (for ALL) every positional argument
    PATTERNS = 'patterns'  # glob patterns of names (Redis psubscribe): '*' stands for any text
    ADDRESS = 'address'  # a (host, port) tuple: the port is the channel
    PORT = 'port'  # a port number
    URL = 'url'  # a URL: its path is the channel
    OBJECT = 'object'  # a library object that carries the name (ChannelTable.WRAPPERS): arroyo's Topic('orders')
    OBJECTS = 'objects'  # a list or tuple of such objects
    ANY_PATH = 'any'  # no channel argument: the server takes every path


class Argument(NamedTuple):
    """Where a call passes a value: a position (ALL: every positional argument, LAST: the last one) or a keyword."""

    ALL = 'all'
    LAST = 'last'

    position: int | str | None
    keyword: str | None = None
    shape: str = Shape.NAME


class LibraryType(NamedTuple):
    """An object a library makes. `creators`: the dotted names (the end of the qualified name) of the calls that make
    it; `factories`: (type, method) pairs, a method of another object of the same library that returns one;
    `classes`: other classes of the library an annotation may name it by (a subclass the library hands out)."""

    library: str  # the top-level module: 'kafka', 'confluent_kafka', 'redis'
    name: str
    creators: tuple = ()
    factories: tuple = ()
    classes: tuple = ()


class Wrapper(NamedTuple):
    """A library object made around a channel: `arroyo.types.Topic(name)`. `argument`: where the call passes it (a
    name, or another wrapper: `Partition(Topic(name), index)`)."""

    library: str
    name: str  # the dotted end of the qualified name of the call that makes it
    argument: Argument


class Endpoint(NamedTuple):
    """One call that sends or receives on a channel.

    kind: a LibraryType name the call is a method of; with callee NEW, the call that makes that type; with kind
    MODULE, a function of the library module itself. `requires`: (Argument, literal) pairs another argument must
    equal for the row to apply. `datagram`: the protocol instead when the socket was made with SOCK_DGRAM.
    """

    MODULE = ''
    NEW = ''

    library: str
    kind: str
    callee: str
    role: str
    protocol: str
    channel: Argument
    method: str = ANY
    requires: tuple = ()
    datagram: str = ''


SEND, RECEIVE = Role.SEND, Role.RECEIVE
MODULE, NEW = Endpoint.MODULE, Endpoint.NEW
KAFKA, AMQP, REDIS, TCP, UDP = Protocol.KAFKA, Protocol.AMQP, Protocol.REDIS, Protocol.TCP, Protocol.UDP
WEBSOCKET = Protocol.WEBSOCKET
TOPIC = Argument(0, 'topic')
TOPICS = Argument(0, 'topics', Shape.NAMES)
EVERY_NAME = Argument(Argument.ALL, None, Shape.NAMES)
ADDRESS = Argument(0, 'address', Shape.ADDRESS)
SERVER_ADDRESS = Argument(0, 'server_address', Shape.ADDRESS)
PORT_THIRD = Argument(2, 'port', Shape.PORT)  # (handler or factory, host, port)
LOCAL_ADDR = Argument(1, 'local_addr', Shape.ADDRESS)  # create_datagram_endpoint(factory, local_addr, remote_addr)
REMOTE_ADDR = Argument(2, 'remote_addr', Shape.ADDRESS)
TOPIC_OBJECT = Argument(1, 'topic', Shape.OBJECT)  # arroyo: (producer or consumer, topic, ...)
DESTINATION = Argument(0, 'destination', Shape.OBJECT)  # arroyo: produce(destination, payload)
TOPIC_OBJECTS = Argument(0, 'topics', Shape.OBJECTS)
DEFAULT_EXCHANGE = ((Argument(0, 'exchange'), ''),)  # pika's default exchange routes by queue name


class ChannelTable:
    """The rows: the objects each library makes, and the calls on them that carry a channel."""

    TYPES = (
        LibraryType('kafka', 'KafkaProducer', ('KafkaProducer',)),
        LibraryType('kafka', 'KafkaConsumer', ('KafkaConsumer',)),
        LibraryType('confluent_kafka', 'Producer', ('Producer', 'SerializingProducer')),
        LibraryType('confluent_kafka', 'Consumer', ('Consumer', 'DeserializingConsumer')),
        LibraryType('aiokafka', 'AIOKafkaProducer', ('AIOKafkaProducer',)),
        LibraryType('aiokafka', 'AIOKafkaConsumer', ('AIOKafkaConsumer',)),
        LibraryType('arroyo', 'KafkaProducer', ('KafkaProducer',)),
        LibraryType('arroyo', 'KafkaConsumer', ('KafkaConsumer',)),
        LibraryType('arroyo', 'FutureTrackingProducer', ('FutureTrackingProducer',)),
        LibraryType('arroyo', 'Producer'),  # arroyo.backends.abstract: the interfaces, only ever annotated
        LibraryType('arroyo', 'Consumer'),
        LibraryType('pika', 'Connection', ('BlockingConnection', 'SelectConnection')),
        # BlockingConnection.channel() returns a BlockingChannel; the asynchronous connections a pika.channel.Channel
        LibraryType('pika', 'Channel', factories=(('Connection', 'channel'),), classes=('BlockingChannel',)),
        LibraryType('redis', 'Redis', ('Redis', 'StrictRedis', 'Redis.from_url', 'redis.from_url')),
        LibraryType('redis', 'PubSub', factories=(('Redis', 'pubsub'),)),
        LibraryType('socket', 'socket', ('socket.socket',)),
        LibraryType('asyncio', 'EventLoop', ('get_running_loop', 'get_event_loop', 'new_event_loop')),
    )

    ENDPOINTS = (
        # kafka-python: KafkaProducer.send(topic, ...); KafkaConsumer(*topics) and .subscribe(topics)
        Endpoint('kafka', 'KafkaProducer', 'send', SEND, KAFKA, TOPIC),
        Endpoint('kafka', 'KafkaConsumer', NEW, RECEIVE, KAFKA, EVERY_NAME),
        Endpoint('kafka', 'KafkaConsumer', 'subscribe', RECEIVE, KAFKA, TOPICS),
        # confluent-kafka: Producer.produce(topic, ...); Consumer.subscribe([topics])
        Endpoint('confluent_kafka', 'Producer', 'produce', SEND, KAFKA, TOPIC),
        Endpoint('confluent_kafka', 'Consumer', 'subscribe', RECEIVE, KAFKA, TOPICS),
        # aiokafka: AIOKafkaProducer.send / send_and_wait(topic); AIOKafkaConsumer(*topics) and .subscribe(topics)
        Endpoint('aiokafka', 'AIOKafkaProducer', 'send', SEND, KAFKA, TOPIC),
        Endpoint('aiokafka', 'AIOKafkaProducer', 'send_and_wait', SEND, KAFKA, TOPIC),
        Endpoint('aiokafka', 'AIOKafkaConsumer', NEW, RECEIVE, KAFKA, EVERY_NAME),
        Endpoint('aiokafka', 'AIOKafkaConsumer', 'subscribe', RECEIVE, KAFKA, TOPICS),
        # arroyo: Producer.produce(destination, payload) to a Topic or Partition (FutureTrackingProducer's is `dest`);
        # Consumer.subscribe(topics);
        # StreamProcessor(consumer, topic, factory) consumes; the Produce strategy and KafkaDlqProducer(producer, topic)
        # produce
        Endpoint('arroyo', 'KafkaProducer', 'produce', SEND, KAFKA, DESTINATION),
        Endpoint('arroyo', 'Producer', 'produce', SEND, KAFKA, DESTINATION),
        Endpoint('arroyo', 'FutureTrackingProducer', 'produce', SEND, KAFKA, Argument(0, 'dest', Shape.OBJECT)),
        Endpoint('arroyo', 'KafkaConsumer', 'subscribe', RECEIVE, KAFKA, TOPIC_OBJECTS),
        Endpoint('arroyo', 'Consumer', 'subscribe', RECEIVE, KAFKA, TOPIC_OBJECTS),
        Endpoint('arroyo', MODULE, 'StreamProcessor', RECEIVE, KAFKA, TOPIC_OBJECT),
        Endpoint('arroyo', MODULE, 'Produce', SEND, KAFKA, TOPIC_OBJECT),
        Endpoint('arroyo', MODULE, 'KafkaDlqProducer', SEND, KAFKA, TOPIC_OBJECT),
        # pika: basic_publish(exchange, routing_key) on the default exchange '' reaches the queue the key names;
        # basic_consume(queue, on_message_callback), and a BlockingChannel's consume(queue) generator
        Endpoint('pika', 'Channel', 'basic_publish', SEND, AMQP, Argument(1, 'routing_key'), requires=DEFAULT_EXCHANGE),
        Endpoint('pika', 'Channel', 'basic_consume', RECEIVE, AMQP, Argument(0, 'queue')),
        Endpoint('pika', 'Channel', 'consume', RECEIVE, AMQP, Argument(0, 'queue')),
        # redis-py: Redis.publish(channel, message); PubSub.subscribe(*channels) and psubscribe(*patterns)
        Endpoint('redis', 'Redis', 'publish', SEND, REDIS, Argument(0, 'channel')),
        Endpoint('redis', 'PubSub', 'subscribe', RECEIVE, REDIS, EVERY_NAME),
        Endpoint('redis', 'PubSub', 'psubscribe', RECEIVE, REDIS, Argument(Argument.ALL, None, Shape.PATTERNS)),
        # socket: sendto(data, address) sends a datagram; connect(address) a stream, unless the socket is SOCK_DGRAM;
        # bind(address) receives; create_connection(address) connects a stream
        Endpoint('socket', 'socket', 'sendto', SEND, UDP, Argument(Argument.LAST, None, Shape.ADDRESS)),
        Endpoint('socket', 'socket', 'connect', SEND, TCP, ADDRESS, datagram=UDP),
        Endpoint('socket', 'socket', 'bind', RECEIVE, TCP, ADDRESS, datagram=UDP),
        Endpoint('socket', MODULE, 'create_connection', SEND, TCP, ADDRESS),
        # socketserver: TCPServer / UDPServer(server_address, handler) and their threading and forking variants
        Endpoint('socketserver', MODULE, 'TCPServer', RECEIVE, TCP, SERVER_ADDRESS),
        Endpoint('socketserver', MODULE, 'ThreadingTCPServer', RECEIVE, TCP, SERVER_ADDRESS),
        Endpoint('socketserver', MODULE, 'ForkingTCPServer', RECEIVE, TCP, SERVER_ADDRESS),
        Endpoint('socketserver', MODULE, 'UDPServer', RECEIVE, UDP, SERVER_ADDRESS),
        Endpoint('socketserver', MODULE, 'ThreadingUDPServer', RECEIVE, UDP, SERVER_ADDRESS),
        Endpoint('socketserver', MODULE, 'ForkingUDPServer', RECEIVE, UDP, SERVER_ADDRESS),
        # asyncio: start_server(handler, host, port) and open_connection(host, port) over TCP; an event loop's
        # create_server / create_connection(factory, host, port), and create_datagram_endpoint(factory,
        # local_addr=(host, port)) to receive or (remote_addr=(host, port)) to send datagrams
        Endpoint('asyncio', MODULE, 'start_server', RECEIVE, TCP, PORT_THIRD),
        Endpoint('asyncio', MODULE, 'open_connection', SEND, TCP, Argument(1, 'port', Shape.PORT)),
        Endpoint('asyncio', 'EventLoop', 'create_server', RECEIVE, TCP, PORT_THIRD),
        Endpoint('asyncio', 'EventLoop', 'create_connection', SEND, TCP, PORT_THIRD),
        Endpoint('asyncio', 'EventLoop', 'create_datagram_endpoint', RECEIVE, UDP, LOCAL_ADDR),
        Endpoint('asyncio', 'EventLoop', 'create_datagram_endpoint', SEND, UDP, REMOTE_ADDR),
        # websockets: connect(uri) opens a connection to the URL's path; serve(handler, host, port) takes every path
        Endpoint('websockets', MODULE, 'connect', SEND, WEBSOCKET, Argument(0, 'uri', Shape.URL), 'CONNECT'),
        Endpoint('websockets', MODULE, 'serve', RECEIVE, WEBSOCKET, Argument(None, None, Shape.ANY_PATH)),
    )

    WRAPPERS = (
        Wrapper('arroyo', 'Topic', Argument(0, 'name')),  # arroyo.types.Topic(name)
        Wrapper('arroyo', 'Partition', Argument(0, 'topic', Shape.OBJECT)),  # arroyo.types.Partition(topic, index)
    )

    @classmethod
    def callees(cls) -> frozenset:
        """Every called name a row can match: method and function names, and the creators of NEW rows."""
        names = {e.callee for e in cls.ENDPOINTS if e.callee}
        for e in cls.ENDPOINTS:
            if e.callee == Endpoint.NEW:
                names |= {c.rsplit('.', 1)[-1] for c in cls.type_named(e.library, e.kind).creators}
        return frozenset(names)

    @classmethod
    def type_named(cls, library, name) -> LibraryType:
        return next(t for t in cls.TYPES if t.library == library and t.name == name)
