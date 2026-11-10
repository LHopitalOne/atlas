import logging

import requests

log = logging.getLogger(__name__)

RATES_API = "https://open.er-api.com/v6/latest"


class FxClient:
    """Exchange rates from the free open.er-api.com endpoint."""

    def __init__(self, base: str = "USD", timeout: float = 5.0) -> None:
        self.base = base
        self.timeout = timeout

    def rate(self, currency: str) -> float:
        if currency == self.base:
            return 1.0
        resp = requests.get(f"{RATES_API}/{self.base}", timeout=self.timeout)
        resp.raise_for_status()
        print(f"RECV O01 GET open.er-api.com /v6/latest/{self.base} status={resp.status_code}", flush=True)
        return float(resp.json()["rates"][currency])
