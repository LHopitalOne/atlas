import requests


class HrApiError(RuntimeError):
    pass


class HrClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"

    def _get(self, path: str) -> dict:
        try:
            resp = self._session.get(f"{self._base_url}{path}", timeout=self._timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise HrApiError(f"GET {path} failed: {exc}") from exc
        return resp.json()

    def salary_band(self, employee_id: int) -> dict:
        return self._get(f"/api/employees/{employee_id}/salary-band/")
