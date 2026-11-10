import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field, HttpUrl

from .settlement import SettlementService
from .store import store

log = logging.getLogger("provider.routes")

router = APIRouter(prefix="/v1")


class MerchantIn(BaseModel):
    name: str
    webhook_url: HttpUrl


class PaymentIn(BaseModel):
    merchant_id: str
    amount_cents: int = Field(gt=0)
    currency: str = "EUR"
    reference: str


class RefundIn(BaseModel):
    amount_cents: int | None = None


def settlement(request: Request) -> SettlementService:
    return request.app.state.settlement


@router.post("/merchants", status_code=201)
async def register_merchant(body: MerchantIn) -> dict:
    merchant = store.add_merchant(body.name, str(body.webhook_url))
    print(f"RECV L01 http POST /v1/merchants name={merchant.name}", flush=True)
    return {"id": merchant.id, "signing_secret": merchant.signing_secret}


@router.post("/payments", status_code=201)
async def create_payment(body: PaymentIn, background: BackgroundTasks, request: Request) -> dict:
    if body.merchant_id not in store.merchants:
        raise HTTPException(status_code=404, detail="unknown merchant")
    payment = store.add_payment(body.merchant_id, body.amount_cents, body.currency, body.reference)
    print(f"RECV L02 http POST /v1/payments payment={payment.id}", flush=True)
    background.add_task(settlement(request).settle, payment.id)
    return {"id": payment.id, "status": payment.status}


@router.post("/payments/{payment_id}/refunds", status_code=201)
async def refund_payment(payment_id: str, body: RefundIn, background: BackgroundTasks, request: Request) -> dict:
    payment = store.payments.get(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="unknown payment")
    if payment.status != "settled":
        raise HTTPException(status_code=409, detail=f"payment is {payment.status}")
    amount = body.amount_cents or payment.amount_cents - payment.refunded_cents
    print(f"RECV L03 http POST /v1/payments/{payment_id}/refunds amount={amount}", flush=True)
    background.add_task(settlement(request).refund, payment, amount)
    return {"payment_id": payment.id, "amount_cents": amount}


@router.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}
