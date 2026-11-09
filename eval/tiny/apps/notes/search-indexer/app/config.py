import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("SEARCH_HOST", "127.0.0.1")
    port: int = int(os.getenv("SEARCH_PORT", "41602"))
    max_results: int = int(os.getenv("SEARCH_MAX_RESULTS", "20"))


settings = Settings()
