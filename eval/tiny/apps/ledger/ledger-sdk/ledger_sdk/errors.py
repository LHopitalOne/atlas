class LedgerError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


class AccountNotFound(LedgerError):
    pass


class InsufficientFunds(LedgerError):
    pass


_BY_CODE = {
    "account_not_found": AccountNotFound,
    "insufficient_funds": InsufficientFunds,
}


def error_from_response(status: int, payload: dict) -> LedgerError:
    code = payload.get("error", "unknown_error")
    cls = _BY_CODE.get(code, LedgerError)
    return cls(status, code, payload.get("message", ""))
