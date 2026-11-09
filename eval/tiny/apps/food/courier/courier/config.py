import os

from dotenv import load_dotenv

load_dotenv()

COURIER_ID = os.getenv("COURIER_ID", "courier-1")
RESTAURANT_API_URL = os.getenv("RESTAURANT_API_URL", "http://localhost:8000")
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/%2F")
PICKUP_QUEUE = os.getenv("PICKUP_QUEUE", "orders.ready_for_pickup")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "5"))
