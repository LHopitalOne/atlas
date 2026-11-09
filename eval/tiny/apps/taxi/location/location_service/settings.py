import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bind_host: str = os.getenv("LOCATION_UDP_HOST", "127.0.0.1")
    bind_port: int = int(os.getenv("LOCATION_UDP_PORT", "41210"))
    dispatch_url: str = os.getenv("DISPATCH_URL", "http://127.0.0.1:41200")
    cell_precision: int = int(os.getenv("CELL_PRECISION", "3"))


settings = Settings()
