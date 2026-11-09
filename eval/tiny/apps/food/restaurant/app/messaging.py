import json
import logging

import pika

from app.settings import get_settings

log = logging.getLogger(__name__)


class PickupPublisher:
    def __init__(self, amqp_url: str, queue: str) -> None:
        self._params = pika.URLParameters(amqp_url)
        self._queue = queue

    def publish_ready(self, payload: dict) -> None:
        connection = pika.BlockingConnection(self._params)
        try:
            channel = connection.channel()
            channel.queue_declare(queue=self._queue, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=self._queue,
                body=json.dumps(payload).encode(),
                properties=pika.BasicProperties(
                    content_type="application/json", delivery_mode=2
                ),
            )
            log.info("published order %s to %s", payload.get("order_id"), self._queue)
        finally:
            connection.close()


def get_publisher() -> PickupPublisher:
    settings = get_settings()
    return PickupPublisher(settings.amqp_url, settings.pickup_queue)
