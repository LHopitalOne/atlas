import logging

from .config import SENDER_ADDRESS

logger = logging.getLogger(__name__)


def render_confirmation(order: dict) -> str:
    lines = "\n".join(
        f"  {line['quantity']} x {line['sku']} @ {line['unit_price']}" for line in order["lines"]
    )
    return f"Thanks for your order #{order['id']}!\n{lines}\nTotal: {order['total']}"


def handle_order_created(event: dict) -> None:
    order = event["order"]
    body = render_confirmation(order)
    logger.info(
        "email from=%s to=%s order=%s (%d chars)",
        SENDER_ADDRESS, order["customer_email"], order["id"], len(body),
    )
