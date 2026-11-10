import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    kafka_brokers: str = os.environ.get("KAFKA_BROKERS", "localhost:46092")
    settle_delay_seconds: float = float(os.environ.get("SETTLE_DELAY_SECONDS", "0.5"))
    webhook_timeout_seconds: float = float(os.environ.get("WEBHOOK_TIMEOUT_SECONDS", "5"))


settings = Settings()
