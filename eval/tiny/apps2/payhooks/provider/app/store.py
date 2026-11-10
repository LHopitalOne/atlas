import secrets
import uuid
from dataclasses import dataclass, field


@dataclass
class Merchant:
    id: str
    name: str
    webhook_url: str
    signing_secret: str


@dataclass
class Payment:
    id: str
    merchant_id: str
    amount_cents: int
    currency: str
    reference: str
    status: str = "pending"
    refunded_cents: int = 0


@dataclass
class Store:
    merchants: dict[str, Merchant] = field(default_factory=dict)
    payments: dict[str, Payment] = field(default_factory=dict)

    def add_merchant(self, name: str, webhook_url: str) -> Merchant:
        merchant = Merchant(
            id=f"mer_{uuid.uuid4().hex[:12]}",
            name=name,
            webhook_url=webhook_url,
            signing_secret=f"whsec_{secrets.token_hex(16)}",
        )
        self.merchants[merchant.id] = merchant
        return merchant

    def add_payment(self, merchant_id: str, amount_cents: int, currency: str, reference: str) -> Payment:
        payment = Payment(
            id=f"pay_{uuid.uuid4().hex[:12]}",
            merchant_id=merchant_id,
            amount_cents=amount_cents,
            currency=currency,
            reference=reference,
        )
        self.payments[payment.id] = payment
        return payment


store = Store()
