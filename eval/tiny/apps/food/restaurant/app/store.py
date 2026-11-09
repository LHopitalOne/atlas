import itertools
from dataclasses import dataclass, field
from threading import Lock

MENUS: dict[int, list[dict]] = {
    1: [
        {"sku": "marg", "name": "Margherita", "price_cents": 1100},
        {"sku": "pepp", "name": "Pepperoni", "price_cents": 1300},
    ],
    2: [
        {"sku": "pho", "name": "Pho Bo", "price_cents": 1450},
        {"sku": "roll", "name": "Spring Rolls", "price_cents": 650},
    ],
}


@dataclass
class Order:
    id: int
    restaurant_id: int
    items: list[str]
    address: str
    status: str = "received"
    history: list[str] = field(default_factory=list)


class OrderStore:
    def __init__(self) -> None:
        self._orders: dict[int, Order] = {}
        self._ids = itertools.count(1001)
        self._lock = Lock()

    def create(self, restaurant_id: int, items: list[str], address: str) -> Order:
        with self._lock:
            order = Order(next(self._ids), restaurant_id, items, address)
            order.history.append(order.status)
            self._orders[order.id] = order
            return order

    def get(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def set_status(self, order: Order, status: str) -> None:
        with self._lock:
            order.status = status
            order.history.append(status)


orders = OrderStore()
