import json
import logging

from aiokafka import AIOKafkaProducer

from .store import Payment
from .topics import REFUNDED_TOPIC, SETTLED_TOPIC

log = logging.getLogger("provider.events")


class EventPublisher:
    def __init__(self, brokers: str) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=brokers,
            value_serializer=lambda value: json.dumps(value).encode(),
            key_serializer=lambda key: key.encode(),
        )

    async def start(self) -> None:
        await self._producer.start()

    async def stop(self) -> None:
        await self._producer.stop()

    async def _publish(self, topic: str, payment: Payment, amount_cents: int) -> None:
        event = {
            "payment_id": payment.id,
            "merchant_id": payment.merchant_id,
            "amount_cents": amount_cents,
            "currency": payment.currency,
        }
        await self._producer.send_and_wait(topic, value=event, key=payment.merchant_id)
        log.info("published %s for %s", topic, payment.id)

    async def payment_settled(self, payment: Payment) -> None:
        await self._publish(SETTLED_TOPIC, payment, payment.amount_cents)

    async def payment_refunded(self, payment: Payment, amount_cents: int) -> None:
        await self._publish(REFUNDED_TOPIC, payment, amount_cents)
