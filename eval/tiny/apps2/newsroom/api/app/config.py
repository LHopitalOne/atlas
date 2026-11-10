"""Settings for the newsroom api, read from the environment."""

import os
from dataclasses import dataclass, field

API_PREFIX = "/api/v1"
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


@dataclass(frozen=True)
class Settings:
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    jobs_queue: str = field(default_factory=lambda: os.getenv("SUMMARY_JOBS_QUEUE", "newsroom:summaries:jobs"))
    done_channel: str = field(
        default_factory=lambda: os.getenv("SUMMARY_DONE_CHANNEL", "newsroom:summaries:done")
    )
    hn_api_base: str = field(default_factory=lambda: os.getenv("HN_API_BASE", HN_API_BASE))
    top_limit: int = field(default_factory=lambda: int(os.getenv("TOP_STORIES_LIMIT", "10")))


settings = Settings()
