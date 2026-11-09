import json
import logging

import redis

logger = logging.getLogger(__name__)


class OrderEventPublisher:
    def __init__(self, redis_url: str, channel: str):
        self._redis = redis.Redis.from_url(redis_url)
        self._channel = channel

    def order_created(self, order: dict) -> None:
        payload = json.dumps({"type": "order.created", "order": order}, default=str)
        try:
            self._redis.publish(self._channel, payload)
        except redis.RedisError:
            logger.exception("could not publish order %s", order["id"])
