"""Orders API."""
from fastapi import FastAPI

from .orders import OrderStore

app = FastAPI()
store = OrderStore()


@app.post('/orders')
def post_order(body: dict):
    return store.create(body['items'])


@app.get('/orders/{order_id}')
def read_order(order_id: str):
    return store.get(order_id)
