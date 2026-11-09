import threading
import uuid
from dataclasses import dataclass


class UnknownSku(Exception):
    pass


class OutOfStock(Exception):
    pass


class UnknownReservation(Exception):
    pass


@dataclass(frozen=True)
class Reservation:
    id: str
    sku: str
    quantity: int
    order_id: str


@dataclass(frozen=True)
class Level:
    sku: str
    on_hand: int
    reserved: int

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


class StockStore:
    """In-memory stock ledger. Good enough until we move to Postgres."""

    def __init__(self, seed: dict[str, int]):
        self._on_hand = dict(seed)
        self._reserved = {sku: 0 for sku in seed}
        self._reservations: dict[str, Reservation] = {}
        self._lock = threading.Lock()

    def level(self, sku: str) -> Level:
        with self._lock:
            return self._level(sku)

    def reserve(self, sku: str, quantity: int, order_id: str) -> tuple[Reservation, Level]:
        with self._lock:
            level = self._level(sku)
            if quantity <= 0 or quantity > level.available:
                raise OutOfStock(f"{sku}: requested {quantity}, available {level.available}")
            reservation = Reservation(uuid.uuid4().hex, sku, quantity, order_id)
            self._reservations[reservation.id] = reservation
            self._reserved[sku] += quantity
            return reservation, self._level(sku)

    def release(self, reservation_id: str) -> tuple[Reservation, Level]:
        with self._lock:
            reservation = self._reservations.pop(reservation_id, None)
            if reservation is None:
                raise UnknownReservation(reservation_id)
            self._reserved[reservation.sku] -= reservation.quantity
            return reservation, self._level(reservation.sku)

    def _level(self, sku: str) -> Level:
        if sku not in self._on_hand:
            raise UnknownSku(sku)
        return Level(sku, self._on_hand[sku], self._reserved[sku])
