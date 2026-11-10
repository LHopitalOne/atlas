import httpx

from reminder_cron.errors import MailerError
from reminder_cron.notes_api import DueNote


class EchoMailer:
    """Sends reminder emails through an HTTP mail relay (httpbin echoes it back)."""

    def __init__(self, url: str, sender: str = "reminders@studynotes.local") -> None:
        self._url = url
        self._sender = sender

    def send_reminder(self, recipient: str, note: DueNote) -> str:
        payload = {
            "from": self._sender,
            "to": recipient,
            "subject": f"Time to review: {note['title']}",
            "text": note["body"],
        }
        try:
            response = httpx.post(self._url, json=payload, timeout=15.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MailerError(f"mail relay rejected reminder for {note['id']}") from exc
        echoed = response.json()
        print(f"RECV T11 https POST httpbin.org{httpx.URL(echoed['url']).path} to={echoed['json']['to']}", flush=True)
        return echoed["url"]
