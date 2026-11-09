import json
import logging

from confluent_kafka import Producer
from django.conf import settings

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, bootstrap_servers: str):
        self._producer = Producer({"bootstrap.servers": bootstrap_servers, "client.id": "hr-app"})

    def publish(self, topic: str, key: str, payload: dict) -> None:
        self._producer.produce(topic, key=key.encode(), value=json.dumps(payload).encode())
        remaining = self._producer.flush(5)
        if remaining:
            logger.warning("%d event(s) to %s not delivered", remaining, topic)


_publisher = None


def get_publisher() -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher(settings.KAFKA_BOOTSTRAP_SERVERS)
    return _publisher


def employee_hired(employee) -> None:
    payload = {
        "employee_id": employee.id,
        "email": employee.email,
        "department": employee.department.name,
        "hired_on": employee.hired_on.isoformat(),
    }
    get_publisher().publish(settings.EMPLOYEE_HIRED_TOPIC, key=str(employee.id), payload=payload)
