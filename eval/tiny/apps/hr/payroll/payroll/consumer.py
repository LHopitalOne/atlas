import json
import logging
import signal

from confluent_kafka import Consumer, KafkaError

from .config import Settings
from .hr_client import HrClient
from .ledger import PayrollLedger

log = logging.getLogger("payroll")


class HiredEventConsumer:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._hr = HrClient(settings.hr_api_url, timeout=settings.http_timeout)
        self._ledger = PayrollLedger()
        self._running = True
        self._consumer = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.consumer_group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        })

    def stop(self, *_):
        self._running = False

    def handle(self, event: dict) -> None:
        employee_id = event["employee_id"]
        band = self._hr.salary_band(employee_id)
        record = self._ledger.enroll(employee_id, band)
        log.info("enrolled employee %s in payroll: %s %s/month", employee_id, record.monthly_gross, record.currency)

    def run(self) -> None:
        self._consumer.subscribe([self._settings.employee_hired_topic])
        log.info("payroll consuming %s", self._settings.employee_hired_topic)
        try:
            while self._running:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() != KafkaError._PARTITION_EOF:
                        log.warning("kafka error: %s", msg.error())
                    continue
                log.info("RECV kafka PUBLISH %s", msg.topic())
                try:
                    self.handle(json.loads(msg.value()))
                except Exception:
                    log.exception("failed to process message at offset %s", msg.offset())
        finally:
            self._consumer.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    consumer = HiredEventConsumer(Settings())
    signal.signal(signal.SIGTERM, consumer.stop)
    signal.signal(signal.SIGINT, consumer.stop)
    consumer.run()
