from decimal import Decimal

import httpx


class ProductNotFound(Exception):
    def __init__(self, product_id: int):
        super().__init__(f"product {product_id} not found")
        self.product_id = product_id


class CatalogClient:
    def __init__(self, base_url: str, timeout: float = 3.0):
        self._http = httpx.Client(base_url=base_url, timeout=timeout)

    def get_product(self, product_id: int) -> dict:
        resp = self._http.get(f"/products/{product_id}")
        if resp.status_code == 404:
            raise ProductNotFound(product_id)
        resp.raise_for_status()
        product = resp.json()
        product["price"] = Decimal(str(product["price"]))
        return product

    def close(self) -> None:
        self._http.close()
