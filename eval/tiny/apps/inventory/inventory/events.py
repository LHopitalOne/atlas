import json
import logging
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import KafkaError

import settings

log = logging.getLogger(__name__)


class StockEventPublisher:
    def __init__(self, bootstrap_servers: str = settings.KAFKA_BOOTSTRAP_SERVERS):
        self._bootstrap_servers = bootstrap_servers
        self._producer: KafkaProducer | None = None

    @property
    def producer(self) -> KafkaProducer:
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                key_serializer=str.encode,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                acks=1,
                retries=3,
            )
        return self._producer

    def stock_low(self, sku: str, available: int, threshold: int) -> None:
        event = {
            "sku": sku,
            "available": available,
            "threshold": threshold,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self._publish(settings.STOCK_LOW_TOPIC, key=sku, value=event)

    def _publish(self, topic: str, key: str, value: dict) -> None:
        try:
            self.producer.send(topic, key=key, value=value).get(timeout=10)
        except KafkaError:
            log.exception("failed to publish to %s", topic)

    def close(self) -> None:
        if self._producer is not None:
            self._producer.close(timeout=5)
