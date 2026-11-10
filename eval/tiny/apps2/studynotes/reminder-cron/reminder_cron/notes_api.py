import json
from datetime import datetime
from typing import TypedDict

import httpx

from reminder_cron.errors import TrpcCallError


class DueNote(TypedDict):
    id: str
    title: str
    body: str
    remindAt: str


class NotesApi:
    """Talks to notes-server's tRPC HTTP endpoints without a tRPC client.

    Queries are GET /trpc/<path>?input=<json>, mutations are POST /trpc/<path>
    with the raw JSON input as the body; results come back as {"result": {"data": ...}}.
    """

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._http = httpx.Client(base_url=f"{base_url}/trpc", timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def due_notes(self, before: datetime) -> list[DueNote]:
        params = {"input": json.dumps({"before": before.isoformat(timespec="milliseconds").replace("+00:00", "Z")})}
        response = self._http.get("/notes.due", params=params)
        return self._unwrap("notes.due", response)

    def mark_reminded(self, note_ids: list[str]) -> int:
        response = self._http.post("/notes.markReminded", json={"ids": note_ids})
        return self._unwrap("notes.markReminded", response)["updated"]

    @staticmethod
    def _unwrap(procedure: str, response: httpx.Response):
        body = response.json()
        if response.is_error or "error" in body:
            message = body.get("error", {}).get("message", response.text)
            raise TrpcCallError(procedure, response.status_code, message)
        return body["result"]["data"]
