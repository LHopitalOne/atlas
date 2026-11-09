import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str = field(default_factory=lambda: _env("KAFKA_BOOTSTRAP_SERVERS", "localhost:41192"))
    employee_hired_topic: str = field(default_factory=lambda: _env("EMPLOYEE_HIRED_TOPIC", "employee.hired"))
    consumer_group: str = field(default_factory=lambda: _env("PAYROLL_CONSUMER_GROUP", "payroll"))
    hr_api_url: str = field(default_factory=lambda: _env("HR_API_URL", "http://127.0.0.1:41100"))
    http_timeout: float = field(default_factory=lambda: float(_env("HR_API_TIMEOUT", "5")))
