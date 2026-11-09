import requests

from courier import config


class RestaurantClient:
    def __init__(self, base_url: str = config.RESTAURANT_API_URL, timeout: float = config.HTTP_TIMEOUT):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": f"courier/{config.COURIER_ID}"})

    def _request(self, method: str, path: str, **kwargs) -> dict:
        response = self._session.request(
            method, f"{self._base_url}{path}", timeout=self._timeout, **kwargs
        )
        response.raise_for_status()
        return response.json()

    def get_order(self, order_id: int) -> dict:
        return self._request("GET", f"/orders/{order_id}")

    def report_status(self, order_id: int, status: str) -> dict:
        return self._request(
            "PUT",
            f"/orders/{order_id}/delivery-status",
            json={"status": status, "courier_id": config.COURIER_ID},
        )
