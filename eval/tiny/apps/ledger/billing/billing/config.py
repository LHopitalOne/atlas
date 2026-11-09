import os


class Settings:
    LEDGER_URL = os.environ.get("LEDGER_URL", "http://127.0.0.1:41410")
    LEDGER_TIMEOUT = float(os.environ.get("LEDGER_TIMEOUT", "5"))
    BILLING_CURRENCY = os.environ.get("BILLING_CURRENCY", "USD")
    REVENUE_ACCOUNT_NAME = os.environ.get("REVENUE_ACCOUNT_NAME", "billing-revenue")
