import os


class Config:
    API_KEY = os.environ.get("PAYMENTS_API_KEY", "dev-payments-key")
    DECLINE_ABOVE_CENTS = int(os.environ.get("PAYMENTS_DECLINE_ABOVE_CENTS", "500000"))
