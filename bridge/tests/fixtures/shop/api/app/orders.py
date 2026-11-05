"""Keeps orders in memory."""
import uuid


class OrderStore:
    def __init__(self):
        self.orders = {}

    def create(self, items):
        order_id = new_id()
        self.orders[order_id] = {'id': order_id, 'items': items}
        return self.orders[order_id]

    def get(self, order_id):
        return self.orders.get(order_id)


def new_id():
    return uuid.uuid4().hex
