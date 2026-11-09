SALARY_BANDS = {
    "B1": (45_000, 60_000),
    "B2": (60_000, 80_000),
    "B3": (80_000, 105_000),
    "B4": (105_000, 140_000),
}
CURRENCY = "EUR"


def band_range(band: str) -> dict:
    low, high = SALARY_BANDS.get(band, SALARY_BANDS["B1"])
    return {"band": band, "min": low, "max": high, "currency": CURRENCY}
