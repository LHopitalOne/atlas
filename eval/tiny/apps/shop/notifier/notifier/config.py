import os

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:41079/0")
ORDER_EVENTS_CHANNEL = os.getenv("ORDER_EVENTS_CHANNEL", "orders.created")
SENDER_ADDRESS = os.getenv("NOTIFIER_FROM", "orders@shop.local")
