import json
import logging
import sys

import pika

from courier import config
from courier.restaurant_client import RestaurantClient

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("courier")


class PickupWorker:
    def __init__(self, client: RestaurantClient) -> None:
        self.client = client

    def handle(self, payload: dict) -> None:
        order_id = payload["order_id"]
        order = self.client.get_order(order_id)
        log.info("picking up order %s for %s", order_id, order["address"])
        self.client.report_status(order_id, "picked_up")
        self.client.report_status(order_id, "delivered")

    def on_message(self, channel, method, properties, body: bytes) -> None:
        print(f"RECV amqp CONSUME {method.routing_key}", flush=True)
        try:
            self.handle(json.loads(body))
        except Exception:
            log.exception("failed to deliver message %s", body)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        channel.basic_ack(delivery_tag=method.delivery_tag)


def main() -> None:
    worker = PickupWorker(RestaurantClient())
    connection = pika.BlockingConnection(pika.URLParameters(config.AMQP_URL))
    channel = connection.channel()
    channel.queue_declare(queue=config.PICKUP_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=config.PICKUP_QUEUE, on_message_callback=worker.on_message)
    log.info("waiting for orders on %s", config.PICKUP_QUEUE)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
