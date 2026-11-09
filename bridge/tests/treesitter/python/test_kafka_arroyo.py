import unittest

from atlas_bridge.core.http import Protocol

from .support import extract

TOPICS = """
from enum import Enum, StrEnum

class Topic(Enum):
    EVENTS = "events"
    OUTCOMES = "outcomes"

class Stream(StrEnum):
    AUDIT = "audit-log"

class Legacy(str, Enum):
    AUDIT = "legacy-audit"
"""

SETTINGS = """
TOPIC_OVERRIDES = {}
"""

CONFIG = """
from django.conf import settings
from app.topics import Topic

def topic_definition(topic, slice_id=None):
    name = topic if isinstance(topic, str) else topic.value
    if slice_id is not None:
        return {"cluster": "sliced", "real_topic_name": settings.SLICED[(name, slice_id)]}
    real = settings.TOPIC_OVERRIDES.get(name, name)
    return {"cluster": "default", "real_topic_name": real}
"""

WRAPPER = """
from arroyo.backends.kafka import KafkaPayload, KafkaProducer

class OneProducer:
    def __init__(self, factory):
        self._producer = None
        self._factory = factory

    def _get(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = self._factory()
        return self._producer

    def produce(self, destination, payload):
        return self._get().produce(destination, payload)
"""


def sends(ex, test=False):
    return {str(c.path) for c in ex.calls if c.protocol == Protocol.KAFKA and c.test == test}


def receives(ex):
    return {str(r.path) for r in ex.routes if r.protocol == Protocol.KAFKA}


class ArroyoTest(unittest.TestCase):
    def test_a_wrapper_class_reached_through_its_instances_and_a_topic_enum(self):
        ex = extract(
            {
                'app/topics.py': TOPICS,
                'app/settings/base.py': SETTINGS,
                'app/config.py': CONFIG,
                'app/producing.py': WRAPPER,
                'app/events.py': """
                from arroyo import Topic as ArroyoTopic
                from app.config import topic_definition
                from app.producing import OneProducer
                from app.topics import Topic

                _events = OneProducer(lambda: None)

                def send_event(payload):
                    topic = topic_definition(Topic.EVENTS)["real_topic_name"]
                    _events.produce(ArroyoTopic(topic), payload)
                """,
                'app/outcomes.py': """
                from arroyo.types import Partition, Topic as ArroyoTopic
                from app.config import topic_definition
                from app.producing import OneProducer
                from app.topics import Topic

                class Outcomes:
                    def __init__(self):
                        self.producer = OneProducer(lambda: None)
                        self.topic = Topic.OUTCOMES

                    def send(self, payload):
                        name = topic_definition(self.topic)["real_topic_name"]
                        self.producer.produce(Partition(ArroyoTopic(name), 0), payload)
                """,
            }
        )
        self.assertEqual(sends(ex), {'/events', '/outcomes'})
        self.assertEqual({c.file for c in ex.calls}, {'app/producing.py'})

    def test_consumers_and_strategies(self):
        ex = extract(
            {
                'app/topics.py': TOPICS,
                'app/consume.py': """
                from arroyo.backends.kafka import KafkaConsumer, KafkaProducer
                from arroyo.processing import StreamProcessor
                from arroyo.processing.strategies import Produce
                from arroyo.types import Topic
                from app.topics import Stream, Topic as Names

                RAW = Topic(Names("events").value)

                def run(factory, config):
                    consumer = KafkaConsumer(config)
                    StreamProcessor(consumer, RAW, factory).run()

                def commit_log(config):
                    consumer = KafkaConsumer(config)
                    consumer.subscribe([Topic("snuba-commit-log")])

                def forward(config, next_step):
                    return Produce(KafkaProducer(config), Topic(Stream.AUDIT), next_step)
                """,
            }
        )
        self.assertEqual(receives(ex), {'/events', '/snuba-commit-log'})
        self.assertEqual(sends(ex), {'/audit-log'})

    def test_future_tracking_producer_takes_dest(self):
        ex = extract(
            {
                'app/send.py': """
                from arroyo.backends.kafka import FutureTrackingProducer
                from arroyo.types import Topic

                def producer() -> FutureTrackingProducer:
                    return FutureTrackingProducer(name="x", producer_factory=None)

                def send(payload):
                    producer().produce(dest=Topic("snuba-items"), payload=payload)
                """,
            }
        )
        self.assertEqual(sends(ex), {'/snuba-items'})

    def test_values_left_unknown_name_no_topic(self):
        ex = extract(
            {
                'app/topics.py': TOPICS,
                'app/registry.py': """
                from app.topics import Topic
                CONSUMERS = {"events": {"topic": Topic.EVENTS}, "outcomes": {"topic": Topic.OUTCOMES}}
                OVERRIDES = {"events": "events-eu"}
                """,
                'app/consume.py': """
                from arroyo.backends.kafka import KafkaConsumer
                from arroyo.processing import StreamProcessor
                from arroyo.types import Topic
                from app.registry import CONSUMERS, OVERRIDES
                from app.topics import Legacy, Topic as Names

                def run(name, factory, config, raw):
                    definition = CONSUMERS[name]
                    StreamProcessor(KafkaConsumer(config), Topic(definition["topic"].value), factory)
                    StreamProcessor(KafkaConsumer(config), Topic(Names.EVENTS), factory)
                    StreamProcessor(KafkaConsumer(config), Topic(OVERRIDES.get(raw, raw)), factory)
                    StreamProcessor(KafkaConsumer(config), Topic(Legacy.AUDIT), factory)
                """,
            }
        )
        self.assertEqual(receives(ex), set())

    def test_a_literal_key_reads_the_entry_and_get_falls_back_only_when_the_key_is_missing(self):
        ex = extract(
            {
                'app/registry.py': """
                CONSUMERS = {"events": {"topic": "events"}, "outcomes": {"topic": "outcomes"}}
                OVERRIDES = {"events": "events-eu"}
                """,
                'app/consume.py': """
                from arroyo.backends.kafka import KafkaConsumer
                from arroyo.types import Topic
                from app.registry import CONSUMERS, OVERRIDES

                def run(config):
                    consumer = KafkaConsumer(config)
                    consumer.subscribe([
                        Topic(CONSUMERS["outcomes"]["topic"]),
                        Topic(OVERRIDES.get("events", "events")),
                        Topic(OVERRIDES.get("spans", "spans")),
                    ])
                """,
            }
        )
        self.assertEqual(receives(ex), {'/outcomes', '/events-eu', '/spans'})

    def test_get_does_not_fall_back_on_a_dict_that_code_adds_entries_to(self):
        ex = extract(
            {
                'app/registry.py': """
                OVERRIDES = {"events": "events-eu"}
                EXTRA = {}

                def configure(region):
                    OVERRIDES["spans"] = "spans-" + region
                    EXTRA.update({"outcomes": region})
                """,
                'app/consume.py': """
                from arroyo.backends.kafka import KafkaConsumer
                from arroyo.types import Topic
                from app.registry import EXTRA, OVERRIDES

                def run(config):
                    KafkaConsumer(config).subscribe([
                        Topic(OVERRIDES.get("spans", "spans")),
                        Topic(EXTRA.get("outcomes", "outcomes")),
                    ])
                """,
            }
        )
        self.assertEqual(receives(ex), set())

    def test_a_consumer_in_test_code_is_no_route(self):
        ex = extract(
            {
                'tests/test_consume.py': """
                from arroyo.backends.kafka import KafkaConsumer
                from arroyo.types import Topic

                def test_consume(config):
                    KafkaConsumer(config).subscribe([Topic("events")])
                """,
            }
        )
        self.assertEqual(receives(ex), set())


if __name__ == '__main__':
    unittest.main()
