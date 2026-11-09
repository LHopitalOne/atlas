from dataclasses import dataclass

import httpx


class PaymentsError(Exception):
    pass


@dataclass(frozen=True)
class Charge:
    id: str
    status: str
    amount_cents: int
    currency: str

    @classmethod
    def from_json(cls, data: dict) -> "Charge":
        return cls(
            id=data["id"],
            status=data["status"],
            amount_cents=data["amount_cents"],
            currency=data["currency"],
        )


class PaymentsClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    async def charge(self, booking_id: str, amount_cents: int, currency: str, customer_email: str) -> Charge:
        payload = {
            "booking_id": booking_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "customer_email": customer_email,
        }
        response = await self._client.post("/charges", json=payload)
        return self._parse(response)

    async def get_charge(self, charge_id: str) -> Charge:
        response = await self._client.get(f"/charges/{charge_id}")
        return self._parse(response)

    async def refund(self, charge_id: str) -> Charge:
        response = await self._client.post(f"/charges/{charge_id}/refund")
        return self._parse(response)

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _parse(response: httpx.Response) -> Charge:
        if response.is_error:
            raise PaymentsError(f"payments returned {response.status_code}: {response.text}")
        return Charge.from_json(response.json())
