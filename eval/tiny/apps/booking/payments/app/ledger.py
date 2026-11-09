import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


class ChargeNotFound(KeyError):
    pass


@dataclass
class Charge:
    id: str
    booking_id: str
    amount_cents: int
    currency: str
    customer_email: str
    status: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class Ledger:
    def __init__(self, decline_above_cents: int) -> None:
        self._charges: dict[str, Charge] = {}
        self._lock = threading.Lock()
        self._decline_above_cents = decline_above_cents

    def create(self, booking_id: str, amount_cents: int, currency: str, customer_email: str) -> Charge:
        status = "declined" if amount_cents > self._decline_above_cents else "succeeded"
        charge = Charge(
            id=f"ch_{uuid.uuid4().hex[:12]}",
            booking_id=booking_id,
            amount_cents=amount_cents,
            currency=currency,
            customer_email=customer_email,
            status=status,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._charges[charge.id] = charge
        return charge

    def get(self, charge_id: str) -> Charge:
        try:
            return self._charges[charge_id]
        except KeyError:
            raise ChargeNotFound(charge_id) from None

    def refund(self, charge_id: str) -> Charge:
        with self._lock:
            charge = self.get(charge_id)
            if charge.status == "succeeded":
                charge.status = "refunded"
            return charge
