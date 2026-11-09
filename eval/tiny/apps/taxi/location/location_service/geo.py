from dataclasses import dataclass


@dataclass
class Fix:
    driver_id: str
    lat: float
    lng: float
    ts: float

    @classmethod
    def parse(cls, data: bytes) -> "Fix":
        driver_id, lat, lng, ts = data.decode().strip().split(",")
        return cls(driver_id, float(lat), float(lng), float(ts))


def cell_for(lat: float, lng: float, precision: int) -> str:
    return f"{round(lat, precision):.{precision}f}:{round(lng, precision):.{precision}f}"
