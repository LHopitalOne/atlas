import unittest

from atlas_bridge.core.http import ANY, Protocol

from .support import extract


def sends(ex):
    return {(c.protocol, str(c.path)) for c in ex.calls if c.protocol != Protocol.HTTP}


def receives(ex):
    return {(r.protocol, str(r.path)) for r in ex.routes if r.protocol != Protocol.HTTP}


class KafkaTest(unittest.TestCase):
    def test_kafka_python_producer_through_a_property_and_a_helper(self):
        ex = extract(
            {
                'svc/settings.py': """
                import os
                TOPIC = os.getenv('STOCK_TOPIC', 'stock.low')
                """,
                'svc/events.py': """
                from kafka import KafkaProducer
                import settings

                class Publisher:
                    def __init__(self):
                        self._producer = None

                    @property
                    def producer(self) -> KafkaProducer:
                        if self._producer is None:
                            self._producer = KafkaProducer(bootstrap_servers='k:9092')
                        return self._producer

                    def low(self, sku):
                        self._publish(settings.TOPIC, key=sku)

                    def _publish(self, topic, key):
                        self.producer.send(topic, key=key).get(timeout=10)
                """,
            }
        )
        self.assertEqual(sends(ex), {(Protocol.KAFKA, '/stock.low')})
        call = ex.calls[0]
        self.assertEqual(
            (call.file, call.line, call.function, call.hints), ('svc/events.py', 19, 'Publisher._publish', frozenset())
        )

    def test_consumers_of_each_library(self):
        ex = extract(
            {
                'a.py': """
                from kafka import KafkaConsumer
                consumer = KafkaConsumer('orders', 'refunds', group_id='g')
                """,
                'b.py': """
                import confluent_kafka

                class Worker:
                    def __init__(self, settings: 'Settings'):
                        self._consumer = confluent_kafka.Consumer({'group.id': 'g'})
                        self._settings = settings

                    def run(self):
                        self._consumer.subscribe([self._settings.topic])
                """,
                'settings.py': """
                import os
                from dataclasses import dataclass, field

                def _env(name, default):
                    return os.environ.get(name, default)

                @dataclass
                class Settings:
                    topic: str = field(default_factory=lambda: _env('TOPIC', 'employee.hired'))
                """,
                'c.py': """
                from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
                from b import Settings

                async def main():
                    consumer = AIOKafkaConsumer('clicks')
                    producer = AIOKafkaProducer()
                    await producer.send_and_wait('views', b'x')
                """,
            }
        )
        self.assertEqual(
            receives(ex), {(Protocol.KAFKA, '/orders'), (Protocol.KAFKA, '/refunds'), (Protocol.KAFKA, '/clicks')}
        )
        self.assertEqual(sends(ex), {(Protocol.KAFKA, '/views')})

    def test_annotated_parameter_type_and_dataclass_default(self):
        ex = extract(
            {
                'svc/consumer.py': """
                from confluent_kafka import Consumer
                from .config import Settings

                class Worker:
                    def __init__(self, settings: Settings):
                        self._settings = settings
                        self._consumer = Consumer({})

                    def run(self):
                        self._consumer.subscribe([self._settings.employee_hired_topic])
                """,
                'svc/config.py': """
                import os
                from dataclasses import dataclass, field

                def _env(name, default):
                    return os.environ.get(name, default)

                @dataclass(frozen=True)
                class Settings:
                    employee_hired_topic: str = field(default_factory=lambda: _env('HIRED', 'employee.hired'))
                """,
            }
        )
        self.assertEqual(receives(ex), {(Protocol.KAFKA, '/employee.hired')})

    def test_a_receiver_not_made_by_the_library_is_not_read(self):
        ex = extract(
            {
                'a.py': """
                from arroyo.backends.kafka import KafkaConsumer, KafkaProducer
                consumer = KafkaConsumer({'group.id': 'g'})
                consumer.subscribe(['orders'])
                KafkaProducer({}).produce('orders', b'x')

                class Bus:
                    def send(self, topic):
                        pass

                Bus().send('orders')
                """,
            }
        )
        self.assertEqual((receives(ex), sends(ex)), (set(), set()))


class AmqpRedisTest(unittest.TestCase):
    def test_pika_default_exchange_through_a_constructor_argument(self):
        ex = extract(
            {
                'app/messaging.py': """
                import pika
                from app.settings import get_settings

                class Publisher:
                    def __init__(self, url, queue):
                        self._params = pika.URLParameters(url)
                        self._queue = queue

                    def publish(self, body):
                        connection = pika.BlockingConnection(self._params)
                        channel = connection.channel()
                        channel.basic_publish(exchange='', routing_key=self._queue, body=body)
                        channel.basic_publish(exchange='events', routing_key='audit', body=body)

                def get_publisher():
                    settings = get_settings()
                    return Publisher(settings.amqp_url, settings.pickup_queue)
                """,
                'app/settings.py': """
                class Settings:
                    amqp_url: str = 'amqp://localhost'
                    pickup_queue: str = 'orders.ready'

                def get_settings():
                    return Settings()
                """,
                'worker.py': """
                import pika
                QUEUE = 'orders.ready'
                connection = pika.BlockingConnection(pika.URLParameters('amqp://x'))
                channel = connection.channel()
                channel.basic_consume(queue=QUEUE, on_message_callback=print)
                """,
            }
        )
        self.assertEqual(sends(ex), {(Protocol.AMQP, '/orders.ready')})
        self.assertEqual(receives(ex), {(Protocol.AMQP, '/orders.ready')})

    def test_redis_publish_through_flask_config_and_subscribe(self):
        ex = extract(
            {
                'app/config.py': """
                import os
                class Config:
                    CHANNEL = os.getenv('ORDER_EVENTS', 'orders.created')
                """,
                'app/__init__.py': """
                from flask import Flask
                from .config import Config
                from .events import Events

                def create_app(config=Config):
                    app = Flask(__name__)
                    app.config.from_object(config)
                    app.extensions['events'] = Events(app.config['CHANNEL'])
                    return app
                """,
                'app/events.py': """
                import redis

                class Events:
                    def __init__(self, channel):
                        self._redis = redis.Redis.from_url('redis://x')
                        self._channel = channel

                    def created(self, payload):
                        self._redis.publish(self._channel, payload)
                """,
                'notifier.py': """
                import redis
                client = redis.Redis()
                pubsub = client.pubsub()
                pubsub.subscribe('orders.created', 'orders.paid')
                pubsub.psubscribe('audit.*')
                """,
            }
        )
        self.assertEqual(sends(ex), {(Protocol.REDIS, '/orders.created')})
        self.assertEqual(
            receives(ex),
            {
                (Protocol.REDIS, '/orders.created'),
                (Protocol.REDIS, '/orders.paid'),
                (Protocol.REDIS, '/audit.{pattern}'),
            },
        )


class SocketTest(unittest.TestCase):
    def test_socket_send_and_receive(self):
        ex = extract(
            {
                'client.py': """
                import os
                import socket
                PORT = int(os.environ.get('PORT', '41210'))

                def replay(data):
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.sendto(data, ('127.0.0.1', PORT))

                def stream():
                    s = socket.socket()
                    s.connect(('127.0.0.1', 9000))
                    socket.create_connection(('db', 5432))
                """,
                'server.py': """
                import socket
                import socketserver
                udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp.bind(('0.0.0.0', 41210))
                server = socketserver.ThreadingTCPServer(('', 9000), object)
                any_port = socket.socket()
                any_port.bind(('', 0))
                """,
                'tests/test_peer.py': """
                import socket

                def test_listens():
                    socket.socket().bind(('', 5555))
                """,
            }
        )
        self.assertEqual(sends(ex), {(Protocol.UDP, '/41210'), (Protocol.TCP, '/9000'), (Protocol.TCP, '/5432')})
        self.assertEqual(receives(ex), {(Protocol.UDP, '/41210'), (Protocol.TCP, '/9000')})

    def test_asyncio_servers_with_settings_from_a_caller(self):
        ex = extract(
            {
                'collector/settings.py': """
                import os
                from dataclasses import dataclass

                @dataclass
                class Settings:
                    host: str
                    tcp_port: int
                    udp_port: int

                def load_settings():
                    return Settings(host='0.0.0.0', tcp_port=int(os.getenv('TCP', '41710')), udp_port=41711)
                """,
                'collector/main.py': """
                import asyncio
                from .settings import Settings, load_settings

                async def start_tcp(settings: Settings):
                    return await asyncio.start_server(print, settings.host, settings.tcp_port)

                async def start_udp(settings: Settings):
                    loop = asyncio.get_running_loop()
                    await loop.create_datagram_endpoint(object, local_addr=(settings.host, settings.udp_port))

                async def main():
                    settings = load_settings()
                    await start_tcp(settings)
                    await start_udp(settings)
                    reader, writer = await asyncio.open_connection('peer', 7000)
                """,
            }
        )
        self.assertEqual(receives(ex), {(Protocol.TCP, '/41710'), (Protocol.UDP, '/41711')})
        self.assertEqual(sends(ex), {(Protocol.TCP, '/7000')})


class WebSocketTest(unittest.TestCase):
    def test_websockets_library_and_framework_routes(self):
        ex = extract(
            {
                'client.py': """
                import websockets
                URL = 'ws://feed:8765/stream'

                async def listen():
                    async with websockets.connect(URL) as ws:
                        await ws.recv()
                """,
                'server.py': """
                import websockets
                from fastapi import FastAPI
                app = FastAPI()

                @app.websocket('/ws')
                async def ws(websocket):
                    pass

                async def main():
                    await websockets.serve(print, '0.0.0.0', 8765)
                """,
            }
        )
        self.assertEqual(sends(ex), {(Protocol.WEBSOCKET, '/stream')})
        self.assertEqual(next(c.method for c in ex.calls if c.protocol == Protocol.WEBSOCKET), 'CONNECT')
        self.assertEqual(receives(ex), {(Protocol.WEBSOCKET, '/ws'), (Protocol.WEBSOCKET, '/{*path}')})
        ws = next(r for r in ex.routes if str(r.path) == '/ws')
        self.assertEqual((ws.methods, ws.framework), (frozenset({ANY}), 'fastapi'))


if __name__ == '__main__':
    unittest.main()
