import logging

import httpx

log = logging.getLogger(__name__)


class DispatchClient:
    def __init__(self, base_url: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=5.0)

    async def driver_nearby(self, driver_id: str, lat: float, lng: float, cell: str) -> None:
        resp = await self._http.post(
            f"/drivers/{driver_id}/nearby",
            json={"lat": lat, "lng": lng, "cell": cell},
        )
        if resp.status_code >= 400:
            log.warning("dispatch rejected nearby update for %s: %s", driver_id, resp.status_code)

    async def aclose(self) -> None:
        await self._http.aclose()
