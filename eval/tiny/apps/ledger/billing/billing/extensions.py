from flask import Flask, current_app
from ledger_sdk import LedgerClient


def init_ledger(app: Flask) -> None:
    app.extensions["ledger"] = LedgerClient(
        app.config["LEDGER_URL"], timeout=app.config["LEDGER_TIMEOUT"]
    )


def ledger() -> LedgerClient:
    return current_app.extensions["ledger"]
