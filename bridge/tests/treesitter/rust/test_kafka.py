import unittest

from atlas_bridge.core.http import Protocol

from .support import RustRepo

PRODUCER = """
use rdkafka::producer::{BaseRecord, FutureProducer, FutureRecord};

const ORDERS: &str = "orders.created";

pub async fn send(producer: &FutureProducer, payload: &str) {
    let record = FutureRecord::to(ORDERS).payload(payload).key("k");
    producer.send(record, 0).await;
}

pub fn audit(payload: &str) {
    let _ = BaseRecord::<(), str>::to("audit").payload(payload);
}

pub fn configured(topic_name: &str, payload: &str) {
    let _ = BaseRecord::<(), str>::to(topic_name).payload(payload);
}
"""

CONSUMER = """
use rdkafka::consumer::{Consumer, StreamConsumer};

pub fn consume(consumer: StreamConsumer, extra: &[&str]) {
    consumer.subscribe(&["payments", "refunds"]).unwrap();
    consumer.subscribe(extra).unwrap();
    consumer.subscribe(&["^audit-.*"]).unwrap();
}
"""


class RdkafkaTest(unittest.TestCase):
    def test_records_name_the_topic_they_are_sent_to(self):
        ex = RustRepo({'src/producer.rs': PRODUCER}).extract()
        sent = {(c.protocol, str(c.path), c.line) for c in ex.calls}
        self.assertEqual(sent, {(Protocol.KAFKA, '/orders.created', 7), (Protocol.KAFKA, '/audit', 12)})

    def test_a_consumer_receives_on_each_topic_it_subscribes_to(self):
        ex = RustRepo({'src/consumer.rs': CONSUMER}).extract()
        self.assertEqual(
            {(r.protocol, str(r.path)) for r in ex.routes},
            {(Protocol.KAFKA, '/payments'), (Protocol.KAFKA, '/refunds')},
        )

    def test_a_subscription_in_test_code_is_no_route(self):
        ex = RustRepo({'tests/consume.rs': CONSUMER}).extract()
        self.assertEqual(ex.routes, [])


if __name__ == '__main__':
    unittest.main()
