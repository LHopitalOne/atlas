from dataclasses import asdict

from flask import Blueprint, abort, current_app, jsonify

items_bp = Blueprint("items", __name__, url_prefix="/<int:order_id>/items")


@items_bp.get("")
def list_items(order_id: int):
    order = current_app.extensions["orders.store"].get(order_id)
    if order is None:
        abort(404)
    return jsonify([asdict(item) for item in order.items])
