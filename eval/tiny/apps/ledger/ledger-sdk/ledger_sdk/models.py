from dataclasses import dataclass


@dataclass(frozen=True)
class Account:
    id: int
    name: str
    currency: str
    allow_overdraft: bool
    balance: int


@dataclass(frozen=True)
class Balance:
    account_id: int
    balance: int
    currency: str


@dataclass(frozen=True)
class Transfer:
    id: int
    source_id: int
    destination_id: int
    amount: int
    reference: str
