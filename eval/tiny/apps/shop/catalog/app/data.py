from decimal import Decimal

from .schemas import Product

PRODUCTS: dict[int, Product] = {
    p.id: p
    for p in [
        Product(id=1, sku="MUG-001", name="Enamel camping mug", price=Decimal("12.50"), stock=40),
        Product(id=2, sku="TSH-014", name="Organic cotton tee", price=Decimal("24.00"), stock=15),
        Product(id=3, sku="BAG-007", name="Canvas tote bag", price=Decimal("18.90"), stock=0),
        Product(id=4, sku="BTL-002", name="Steel water bottle", price=Decimal("21.00"), stock=8),
    ]
}


def find_product(product_id: int) -> Product | None:
    return PRODUCTS.get(product_id)
