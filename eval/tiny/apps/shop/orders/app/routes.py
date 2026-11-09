from decimal import Decimal

from flask import Blueprint, abort, current_app, jsonify, request

from .catalog_client import ProductNotFound

bp = Blueprint("orders", __name__, url_prefix="/orders")


@bp.post("")
def create_order():
    body = request.get_json(silent=True) or {}
    items = body.get("items") or []
    email = body.get("customer_email")
    if not items or not email:
        abort(400, description="customer_email and items are required")

    catalog = current_app.extensions["catalog"]
    lines, total = [], Decimal("0")
    for item in items:
        quantity = int(item.get("quantity", 1))
        try:
            product = catalog.get_product(int(item["product_id"]))
        except ProductNotFound as exc:
            abort(422, description=str(exc))
        if product["stock"] < quantity:
            abort(409, description=f"not enough stock for {product['sku']}")
        line_total = product["price"] * quantity
        total += line_total
        lines.append({
            "product_id": product["id"],
            "sku": product["sku"],
            "quantity": quantity,
            "unit_price": str(product["price"]),
        })

    order = current_app.extensions["order_store"].add(email, lines, total)
    current_app.extensions["order_events"].order_created(order)
    return jsonify(order), 201


@bp.get("/<int:order_id>")
def get_order(order_id: int):
    order = current_app.extensions["order_store"].get(order_id)
    if order is None:
        abort(404, description="order not found")
    return jsonify(order)
