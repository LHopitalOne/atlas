import hashlib
import hmac
import json
import logging
import time
import uuid

import httpx

from .store import Merchant

log = logging.getLogger("provider.webhooks")

SIGNATURE_HEADER = "Payhooks-Signature"


def sign(secret: str, timestamp: int, body: bytes) -> str:
    signed_payload = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


class WebhookDispatcher:
    def __init__(self, timeout: float) -> None:
        self._http = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "payhooks-webhooks/1.0"})

    async def close(self) -> None:
        await self._http.aclose()

    async def deliver(self, merchant: Merchant, event_type: str, data: dict) -> None:
        event = {"id": f"evt_{uuid.uuid4().hex[:12]}", "type": event_type, "data": data}
        body = json.dumps(event).encode()
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: sign(merchant.signing_secret, int(time.time()), body),
        }
        response = await self._http.post(merchant.webhook_url, content=body, headers=headers)
        log.info("webhook %s -> %s: %s", event_type, merchant.webhook_url, response.status_code)
