import itertools
import threading
from datetime import datetime, timezone


class OrderStore:
    """In-memory storage until we move orders to Postgres."""

    def __init__(self):
        self._orders: dict[int, dict] = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def add(self, customer_email: str, lines: list[dict], total) -> dict:
        with self._lock:
            order_id = next(self._ids)
            order = {
                "id": order_id,
                "customer_email": customer_email,
                "lines": lines,
                "total": str(total),
                "status": "created",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._orders[order_id] = order
            return order

    def get(self, order_id: int) -> dict | None:
        return self._orders.get(order_id)
