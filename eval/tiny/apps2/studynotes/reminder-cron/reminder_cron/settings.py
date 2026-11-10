import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    notes_api_url: str
    mailer_url: str
    interval_seconds: int
    recipient: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            notes_api_url=os.environ.get("NOTES_API_URL", "http://127.0.0.1:45010"),
            mailer_url=os.environ.get("MAILER_URL", "https://httpbin.org/anything/email"),
            interval_seconds=int(os.environ.get("REMINDER_INTERVAL", "300")),
            recipient=os.environ.get("REMINDER_RECIPIENT", "student@example.edu"),
        )
