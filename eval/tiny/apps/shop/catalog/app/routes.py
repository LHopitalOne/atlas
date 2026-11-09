from fastapi import APIRouter, HTTPException, Query

from .data import PRODUCTS, find_product
from .schemas import Product

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[Product])
def list_products(in_stock: bool = Query(False)) -> list[Product]:
    products = list(PRODUCTS.values())
    if in_stock:
        products = [p for p in products if p.stock > 0]
    return products


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: int) -> Product:
    product = find_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product
