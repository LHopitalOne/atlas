from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PayrollRecord:
    employee_id: int
    band: str
    monthly_gross: Decimal
    currency: str


class PayrollLedger:
    def __init__(self):
        self._records: dict[int, PayrollRecord] = {}

    def enroll(self, employee_id: int, band: dict) -> PayrollRecord:
        midpoint = Decimal(band["min"] + band["max"]) / 2
        record = PayrollRecord(
            employee_id=employee_id,
            band=band["band"],
            monthly_gross=(midpoint / 12).quantize(Decimal("0.01")),
            currency=band["currency"],
        )
        self._records[employee_id] = record
        return record
