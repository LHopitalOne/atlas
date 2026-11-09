import itertools
import threading
from dataclasses import dataclass

from flask import current_app
from ledger_sdk import Account, Balance, Transfer

from billing.extensions import ledger


@dataclass
class Customer:
    id: int
    email: str
    ledger_account_id: int


class BillingService:
    def __init__(self) -> None:
        self._customers: dict[int, Customer] = {}
        self._ids = itertools.count(1)
        self._revenue_account_id: int | None = None
        self._lock = threading.Lock()

    def register_customer(self, email: str) -> Customer:
        account = ledger().create_account(
            f"customer:{email}",
            currency=current_app.config["BILLING_CURRENCY"],
            allow_overdraft=True,
        )
        customer = Customer(next(self._ids), email, account.id)
        self._customers[customer.id] = customer
        return customer

    def customer(self, customer_id: int) -> Customer | None:
        return self._customers.get(customer_id)

    def account(self, customer: Customer) -> Account:
        return ledger().get_account(customer.ledger_account_id)

    def balance(self, customer: Customer) -> Balance:
        return ledger().get_balance(customer.ledger_account_id)

    def charge(self, customer: Customer, amount_cents: int, invoice_id: str) -> Transfer:
        return ledger().create_transfer(
            customer.ledger_account_id,
            self._revenue_account(),
            amount_cents,
            reference=invoice_id,
        )

    def charges(self, customer: Customer) -> list[Transfer]:
        return [
            t
            for t in ledger().list_transfers(customer.ledger_account_id)
            if t.source_id == customer.ledger_account_id
        ]

    def _revenue_account(self) -> int:
        with self._lock:
            if self._revenue_account_id is None:
                account = ledger().create_account(
                    current_app.config["REVENUE_ACCOUNT_NAME"],
                    currency=current_app.config["BILLING_CURRENCY"],
                )
                self._revenue_account_id = account.id
            return self._revenue_account_id


billing = BillingService()
