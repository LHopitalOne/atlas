class ReminderError(Exception):
    """Base error for the reminder job."""


class TrpcCallError(ReminderError):
    def __init__(self, procedure: str, status: int, message: str) -> None:
        super().__init__(f"tRPC {procedure} failed with {status}: {message}")
        self.procedure = procedure
        self.status = status


class MailerError(ReminderError):
    pass
