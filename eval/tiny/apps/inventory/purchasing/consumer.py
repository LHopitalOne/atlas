import json
import logging

import requests
from kafka import KafkaConsumer

import settings
from warehouse_client import WarehouseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("purchasing")


def handle_stock_low(event: dict, warehouse: WarehouseClient) -> None:
    sku = event["sku"]
    level = warehouse.get_stock(sku)
    if level["available"] > event["threshold"]:
        log.info("%s recovered to %s, skipping restock", sku, level["available"])
        return

    quantity = settings.RESTOCK_TARGET_LEVEL - level["onHand"]
    if quantity <= 0:
        return
    order = warehouse.place_restock_order(
        sku, quantity, reason=f"available {level['available']} <= {event['threshold']}"
    )
    log.info("placed restock order %s: %s x %s", order["id"], quantity, sku)


def main() -> None:
    consumer = KafkaConsumer(
        settings.STOCK_LOW_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
    )
    warehouse = WarehouseClient()
    log.info("purchasing consuming %s", settings.STOCK_LOW_TOPIC)

    for message in consumer:
        log.info("RECV kafka PUBLISH %s", message.topic)
        try:
            handle_stock_low(message.value, warehouse)
        except requests.RequestException:
            log.exception("restock failed for %s", message.value.get("sku"))


if __name__ == "__main__":
    main()
