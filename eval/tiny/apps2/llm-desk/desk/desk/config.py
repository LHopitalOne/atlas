from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DESK_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 42000

    openrouter_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    openrouter_url: str = "https://openrouter.ai"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    jev_model: str = "typesafe/jev-1.14"
    draft_model: str = "openai/gpt-4o-mini"
    draft_max_tokens: int = 120

    redis_url: str = "redis://localhost:6379/0"
    triaged_stream: str = "desk.tickets.triaged"

    teams: tuple[str, ...] = ("billing", "infrastructure", "accounts")


@lru_cache
def get_settings() -> Settings:
    return Settings()
