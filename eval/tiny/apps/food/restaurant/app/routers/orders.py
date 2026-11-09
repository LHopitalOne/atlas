from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.messaging import PickupPublisher, get_publisher
from app.store import MENUS, Order, orders

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderIn(BaseModel):
    restaurant_id: int
    items: list[str]
    address: str


class DeliveryStatusIn(BaseModel):
    status: str
    courier_id: str


def _load(order_id: int) -> Order:
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(body: OrderIn) -> dict:
    known = {item["sku"] for item in MENUS.get(body.restaurant_id, [])}
    unknown = [sku for sku in body.items if sku not in known]
    if not known or unknown:
        raise HTTPException(status_code=422, detail=f"unknown items: {unknown}")
    order = orders.create(body.restaurant_id, body.items, body.address)
    return asdict(order)


@router.get("/{order_id}")
def get_order(order_id: int) -> dict:
    return asdict(_load(order_id))


@router.post("/{order_id}/ready")
def mark_ready(order_id: int, publisher: PickupPublisher = Depends(get_publisher)) -> dict:
    order = _load(order_id)
    orders.set_status(order, "ready_for_pickup")
    publisher.publish_ready(
        {"order_id": order.id, "restaurant_id": order.restaurant_id, "address": order.address}
    )
    return asdict(order)


@router.put("/{order_id}/delivery-status")
def update_delivery_status(order_id: int, body: DeliveryStatusIn) -> dict:
    order = _load(order_id)
    orders.set_status(order, body.status)
    return asdict(order)
