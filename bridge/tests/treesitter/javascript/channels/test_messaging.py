import unittest

from atlas_bridge.core.http import ANY, Protocol

from .support import Channels


def channels(found):
    return [(p, m, path) for p, m, path, _, _ in found.calls], [(p, path) for p, _, path, _, _ in found.routes]


class KafkaTest(unittest.TestCase):
    def test_producer_and_consumer(self):
        found = Channels.of(
            "const { Kafka } = require('kafkajs');\n"
            "const TOPIC = process.env.ORDERS_TOPIC ?? 'orders.created';\n"
            "const kafka = new Kafka({ brokers: ['kafka:9092'] });\n"
            'const producer = kafka.producer();\n'
            'async function emit(order) {\n'
            '  await producer.send({ topic: TOPIC, messages: [{ value: JSON.stringify(order) }] });\n'
            '}\n'
            'async function listen(consumer, res) {\n'
            "  await consumer.subscribe({ topic: 'payments.settled', fromBeginning: true });\n"
            "  await consumer.subscribe({ topics: ['refunds', 'chargebacks'] });\n"
            "  res.send('ok');\n"  # not a topic: kafkajs takes an options object
            '}\n',
        )
        k = Protocol.KAFKA
        calls, routes = channels(found)
        self.assertEqual(calls, [(k, ANY, '/orders.created')])
        self.assertEqual(routes, [(k, '/payments.settled'), (k, '/refunds'), (k, '/chargebacks')])
        self.assertEqual(found.extraction.routes[0].framework, 'kafkajs')
        self.assertEqual(found.extraction.routes[0].handler, 'listen')

    def test_a_file_that_does_not_import_the_library_is_not_read(self):
        found = Channels.of("producer.send({ topic: 'orders', messages: [] });\n")
        self.assertEqual(found.calls, [])

    def test_a_wrapper_sends_on_each_topic_its_callers_pass(self):
        found = Channels.of(
            "import { Kafka } from 'kafkajs';\n"
            'const producer = new Kafka({}).producer();\n'
            'export async function publish(topic, event) {\n'
            '  await producer.send({ topic, messages: [{ value: JSON.stringify(event) }] });\n'
            '}\n'
            "export const hired = (e) => publish('employee.hired', e);\n"
            "export const left = (e) => publish('employee.left', e);\n",
        )
        self.assertEqual(
            [(path, line) for _, _, path, _, line in found.calls], [('/employee.hired', 4), ('/employee.left', 4)]
        )


class AmqpTest(unittest.TestCase):
    def test_queue_routing_key_and_consumer(self):
        found = Channels.of(
            "import amqp from 'amqplib';\n"
            "const QUEUE = 'invoices';\n"
            'export async function run(ch, body) {\n'
            '  ch.sendToQueue(QUEUE, Buffer.from(body));\n'
            "  ch.publish('billing', 'invoice.paid', Buffer.from(body));\n"
            "  ch.publish('billing', 'x');\n"  # too few arguments for amqplib's publish
            "  await ch.consume('receipts', (msg) => ch.ack(msg));\n"
            '}\n',
        )
        a = Protocol.AMQP
        self.assertEqual(channels(found), ([(a, ANY, '/invoices'), (a, ANY, '/invoice.paid')], [(a, '/receipts')]))


class RedisTest(unittest.TestCase):
    def test_publish_and_subscribe(self):
        found = Channels.of(
            "import Redis from 'ioredis';\n"
            "const CHANNEL = process.env.EVENTS_CHANNEL || 'orders.created';\n"
            'const pub = new Redis();\n'
            'const sub = new Redis();\n'
            'pub.publish(CHANNEL, JSON.stringify({ id: 1 }));\n'
            "sub.subscribe('orders.created', 'orders.cancelled', (err) => {});\n",
        )
        r = Protocol.REDIS
        self.assertEqual(
            channels(found), ([(r, ANY, '/orders.created')], [(r, '/orders.created'), (r, '/orders.cancelled')])
        )

    def test_node_redis_and_dynamic_channels(self):
        found = Channels.of(
            "const { createClient } = require('redis');\n"
            'async function main(client, room) {\n'
            "  await client.subscribe('alerts', (message) => console.log(message));\n"
            '  await client.publish(`room:${room}`, "hi");\n'  # depends on the room: not one channel
            '}\n',
        )
        self.assertEqual(channels(found), ([], [(Protocol.REDIS, '/alerts')]))


if __name__ == '__main__':
    unittest.main()
