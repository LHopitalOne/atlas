import os


class Config:
    CATALOG_URL = os.getenv("CATALOG_URL", "http://127.0.0.1:41001")
    CATALOG_TIMEOUT = float(os.getenv("CATALOG_TIMEOUT", "3"))
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:41079/0")
    ORDER_EVENTS_CHANNEL = os.getenv("ORDER_EVENTS_CHANNEL", "orders.created")
