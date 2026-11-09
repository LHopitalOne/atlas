from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOKING_", env_file=".env", extra="ignore")

    payments_url: str = "http://127.0.0.1:41820"
    payments_api_key: str = "dev-payments-key"
    payments_timeout: float = 5.0
    currency: str = "EUR"
    cors_origins: list[str] = ["http://127.0.0.1:41830", "http://localhost:41830"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
