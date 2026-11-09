from flask import Blueprint, abort, current_app, jsonify, request

from .ledger import ChargeNotFound, Ledger

bp = Blueprint("charges", __name__, url_prefix="/charges")


def _ledger() -> Ledger:
    return current_app.extensions["ledger"]


@bp.before_request
def require_api_key() -> None:
    expected = f"Bearer {current_app.config['API_KEY']}"
    if request.headers.get("Authorization") != expected:
        abort(401)


@bp.errorhandler(ChargeNotFound)
def charge_not_found(err: ChargeNotFound):
    return jsonify(error="charge_not_found", charge_id=str(err.args[0])), 404


@bp.post("")
def create_charge():
    body = request.get_json(force=True)
    missing = [k for k in ("booking_id", "amount_cents", "currency", "customer_email") if k not in body]
    if missing:
        return jsonify(error="missing_fields", fields=missing), 400
    charge = _ledger().create(
        booking_id=body["booking_id"],
        amount_cents=int(body["amount_cents"]),
        currency=body["currency"],
        customer_email=body["customer_email"],
    )
    return jsonify(charge.to_dict()), 201


@bp.get("/<charge_id>")
def get_charge(charge_id: str):
    return jsonify(_ledger().get(charge_id).to_dict())


@bp.post("/<charge_id>/refund")
def refund_charge(charge_id: str):
    return jsonify(_ledger().refund(charge_id).to_dict())
