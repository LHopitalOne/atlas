import time
from datetime import UTC, datetime

from reminder_cron.errors import MailerError
from reminder_cron.mailer import EchoMailer
from reminder_cron.notes_api import NotesApi
from reminder_cron.settings import Settings


class ReminderJob:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api = NotesApi(settings.notes_api_url)
        self._mailer = EchoMailer(settings.mailer_url)

    def run_once(self) -> int:
        due = self._api.due_notes(before=datetime.now(UTC))
        sent: list[str] = []
        for note in due:
            try:
                self._mailer.send_reminder(self._settings.recipient, note)
            except MailerError as exc:
                print(f"reminder skipped: {exc}", flush=True)
                continue
            sent.append(note["id"])
        updated = self._api.mark_reminded(sent) if sent else 0
        print(f"reminders: due={len(due)} sent={len(sent)} marked={updated}", flush=True)
        return updated

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self._settings.interval_seconds)

    def close(self) -> None:
        self._api.close()
