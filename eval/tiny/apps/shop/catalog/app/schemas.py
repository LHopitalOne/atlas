from decimal import Decimal

from pydantic import BaseModel


class Product(BaseModel):
    id: int
    sku: str
    name: str
    price: Decimal
    currency: str = "EUR"
    stock: int
