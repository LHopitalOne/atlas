from __future__ import annotations

import requests

from ledger_sdk._version import __version__
from ledger_sdk.errors import error_from_response
from ledger_sdk.models import Account, Balance, Transfer

DEFAULT_TIMEOUT = 5.0


class LedgerClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.setdefault("User-Agent", f"ledger-sdk-python/{__version__}")

    def ping(self) -> bool:
        return self._request("GET", "/health").get("status") == "ok"

    def create_account(
        self, name: str, *, currency: str | None = None, allow_overdraft: bool = False
    ) -> Account:
        body = {"name": name, "allow_overdraft": allow_overdraft}
        if currency:
            body["currency"] = currency
        return Account(**self._request("POST", "/accounts", json=body))

    def get_account(self, account_id: int) -> Account:
        return Account(**self._request("GET", f"/accounts/{account_id}"))

    def get_balance(self, account_id: int) -> Balance:
        return Balance(**self._request("GET", f"/accounts/{account_id}/balance"))

    def list_transfers(self, account_id: int) -> list[Transfer]:
        rows = self._request("GET", f"/accounts/{account_id}/transfers")
        return [Transfer(**row) for row in rows]

    def create_transfer(
        self, source_id: int, destination_id: int, amount: int, *, reference: str = ""
    ) -> Transfer:
        body = {
            "source_id": source_id,
            "destination_id": destination_id,
            "amount": amount,
            "reference": reference,
        }
        return Transfer(**self._request("POST", "/transfers", json=body))

    def _request(self, method: str, path: str, **kwargs):
        response = self._session.request(
            method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
        )
        if response.status_code >= 400:
            raise error_from_response(response.status_code, response.json())
        return response.json()
