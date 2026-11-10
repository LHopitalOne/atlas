from flask import Blueprint, abort, current_app, jsonify, request

from app.blueprints.items import items_bp
from app.clients.users import BuyerNotEligible
from app.store import LineItem

orders_bp = Blueprint("orders", __name__, url_prefix="/v1/orders")
orders_bp.register_blueprint(items_bp)


@orders_bp.get("")
def list_orders():
    buyer = request.args.get("buyer", type=int)
    orders = current_app.extensions["orders.store"].filter(buyer_id=buyer)
    return jsonify([o.to_dict() for o in orders])


@orders_bp.post("")
def place_order():
    payload = request.get_json(force=True)
    buyer_id = int(payload["buyer_id"])
    currency = payload.get("currency", "USD").upper()

    try:
        current_app.extensions["orders.users"].verify_buyer(buyer_id)
    except BuyerNotEligible as exc:
        return jsonify(error=str(exc)), 422

    items = [LineItem(i["sku"], int(i["qty"]), float(i["price_usd"])) for i in payload["items"]]
    rate = current_app.extensions["orders.fx"].rate(currency)
    total = sum(i.qty * i.price_usd for i in items) * rate
    order = current_app.extensions["orders.store"].add(buyer_id, currency, total, items)
    return jsonify(order.to_dict()), 201


@orders_bp.get("/<int:order_id>")
def get_order(order_id: int):
    order = current_app.extensions["orders.store"].get(order_id)
    if order is None:
        abort(404)
    return jsonify(order.to_dict())
