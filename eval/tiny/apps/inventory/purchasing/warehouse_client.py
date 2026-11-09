import requests

import settings


class WarehouseClient:
    def __init__(self, base_url: str = settings.WAREHOUSE_API_URL, timeout: float = settings.HTTP_TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "purchasing/1.0", "Accept": "application/json"})

    def get_stock(self, sku: str) -> dict:
        return self._request("GET", f"/stock/{sku}")

    def place_restock_order(self, sku: str, quantity: int, reason: str) -> dict:
        return self._request("POST", "/restock-orders", json={"sku": sku, "quantity": quantity, "reason": reason})

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response.json()
