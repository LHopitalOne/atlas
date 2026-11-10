import requests


class BuyerNotEligible(Exception):
    """The users service refused the buyer (unknown or unverified)."""


class UsersClient:
    """Direct service-to-service client for the users service (bypasses the edge gateway)."""

    def __init__(self, base_url: str, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Accept"] = "application/json"

    def verify_buyer(self, buyer_id: int) -> dict:
        url = f"{self.base_url}/internal/buyers/{buyer_id}/verify"
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code == 404:
            raise BuyerNotEligible(f"buyer {buyer_id} does not exist")
        resp.raise_for_status()
        body = resp.json()
        if not body.get("eligible"):
            raise BuyerNotEligible(f"buyer {buyer_id} is not verified")
        return body
