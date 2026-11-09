import uuid
from dataclasses import asdict

from flask import Blueprint, abort, jsonify, request
from ledger_sdk import InsufficientFunds, LedgerError

from billing.extensions import ledger
from billing.service import billing

bp = Blueprint("customers", __name__)


@bp.get("/healthz")
def healthz():
    try:
        ledger_ok = ledger().ping()
    except LedgerError:
        ledger_ok = False
    return jsonify(status="ok", ledger=ledger_ok)


@bp.post("/customers")
def create_customer():
    payload = request.get_json(force=True)
    customer = billing.register_customer(payload["email"])
    return jsonify(asdict(customer)), 201


def _load(customer_id: int):
    customer = billing.customer(customer_id)
    if customer is None:
        abort(404)
    return customer


@bp.get("/customers/<int:customer_id>")
def show_customer(customer_id: int):
    customer = _load(customer_id)
    account = billing.account(customer)
    return jsonify(customer=asdict(customer), account=asdict(account))


@bp.get("/customers/<int:customer_id>/balance")
def customer_balance(customer_id: int):
    balance = billing.balance(_load(customer_id))
    return jsonify(asdict(balance))


@bp.post("/customers/<int:customer_id>/charges")
def charge_customer(customer_id: int):
    customer = _load(customer_id)
    payload = request.get_json(force=True)
    invoice_id = payload.get("invoice_id") or f"inv_{uuid.uuid4().hex[:12]}"
    try:
        transfer = billing.charge(customer, int(payload["amount_cents"]), invoice_id)
    except InsufficientFunds as exc:
        return jsonify(error=exc.code), 402
    return jsonify(asdict(transfer)), 201


@bp.get("/customers/<int:customer_id>/charges")
def list_charges(customer_id: int):
    return jsonify([asdict(t) for t in billing.charges(_load(customer_id))])
