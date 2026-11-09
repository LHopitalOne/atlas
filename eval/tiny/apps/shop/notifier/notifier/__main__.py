import json
import logging

import redis

from .config import ORDER_EVENTS_CHANNEL, REDIS_URL
from .handlers import handle_order_created

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("notifier")


def main() -> None:
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(ORDER_EVENTS_CHANNEL)
    logger.info("subscribed to %s", ORDER_EVENTS_CHANNEL)

    for message in pubsub.listen():
        logger.info("RECV redis PUBLISH %s", message["channel"])
        try:
            handle_order_created(json.loads(message["data"]))
        except (KeyError, ValueError):
            logger.exception("bad event on %s", message["channel"])


if __name__ == "__main__":
    main()
