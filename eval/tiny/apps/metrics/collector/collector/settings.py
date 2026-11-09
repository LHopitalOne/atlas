import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bind_host: str
    tcp_port: int
    statsd_port: int
    http_port: int
    retention: int
    log_level: str


def load_settings() -> Settings:
    return Settings(
        bind_host=os.getenv("COLLECTOR_BIND_HOST", "127.0.0.1"),
        tcp_port=int(os.getenv("COLLECTOR_TCP_PORT", "41710")),
        statsd_port=int(os.getenv("COLLECTOR_STATSD_PORT", "41711")),
        http_port=int(os.getenv("COLLECTOR_HTTP_PORT", "41712")),
        retention=int(os.getenv("COLLECTOR_RETENTION", "1000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
