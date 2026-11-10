from dataclasses import asdict, dataclass, field
from itertools import count
from threading import Lock


@dataclass
class LineItem:
    sku: str
    qty: int
    price_usd: float


@dataclass
class Order:
    id: int
    buyer_id: int
    currency: str
    total: float
    items: list[LineItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class OrderStore:
    def __init__(self) -> None:
        self._orders: dict[int, Order] = {}
        self._ids = count(1)
        self._lock = Lock()
        self.add(buyer_id=2, currency="USD", total=19.0, items=[LineItem("SKU-102", 1, 19.0)])

    def add(self, buyer_id: int, currency: str, total: float, items: list[LineItem]) -> Order:
        with self._lock:
            order = Order(next(self._ids), buyer_id, currency, round(total, 2), items)
            self._orders[order.id] = order
            return order

    def get(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def filter(self, buyer_id: int | None = None) -> list[Order]:
        orders = list(self._orders.values())
        if buyer_id is None:
            return orders
        return [o for o in orders if o.buyer_id == buyer_id]
