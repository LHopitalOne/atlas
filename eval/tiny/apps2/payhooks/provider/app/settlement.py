import asyncio
import logging

from .events import EventPublisher
from .store import Payment, store
from .webhooks import WebhookDispatcher

log = logging.getLogger("provider.settlement")


class SettlementService:
    def __init__(self, publisher: EventPublisher, webhooks: WebhookDispatcher, delay: float) -> None:
        self._publisher = publisher
        self._webhooks = webhooks
        self._delay = delay

    @staticmethod
    def _payload(payment: Payment) -> dict:
        return {
            "payment_id": payment.id,
            "reference": payment.reference,
            "amount_cents": payment.amount_cents,
            "refunded_cents": payment.refunded_cents,
            "currency": payment.currency,
            "status": payment.status,
        }

    async def settle(self, payment_id: str) -> None:
        await asyncio.sleep(self._delay)
        payment = store.payments[payment_id]
        payment.status = "settled"
        await self._publisher.payment_settled(payment)
        merchant = store.merchants[payment.merchant_id]
        await self._webhooks.deliver(merchant, "payment.settled", self._payload(payment))

    async def refund(self, payment: Payment, amount_cents: int) -> None:
        payment.refunded_cents += amount_cents
        payment.status = "refunded" if payment.refunded_cents >= payment.amount_cents else "partially_refunded"
        await self._publisher.payment_refunded(payment, amount_cents)
        merchant = store.merchants[payment.merchant_id]
        await self._webhooks.deliver(merchant, "payment.refunded", self._payload(payment))
