from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    restaurant_host: str = "127.0.0.1"
    restaurant_port: int = 41510
    amqp_url: str = "amqp://guest:guest@localhost:5672/%2F"
    pickup_queue: str = "orders.ready_for_pickup"


@lru_cache
def get_settings() -> Settings:
    return Settings()
