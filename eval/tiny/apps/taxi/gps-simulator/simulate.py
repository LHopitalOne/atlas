"""Replay a short GPS track for one or more drivers over UDP."""
import argparse
import os
import socket
import time

LOCATION_HOST = os.environ.get("LOCATION_HOST", "127.0.0.1")
LOCATION_PORT = int(os.environ.get("LOCATION_PORT", "41210"))

TRACK = [
    (40.7410, -73.9897),
    (40.7425, -73.9881),
    (40.7441, -73.9866),
    (40.7458, -73.9850),
]


def encode_fix(driver_id: str, lat: float, lng: float) -> bytes:
    return f"{driver_id},{lat:.6f},{lng:.6f},{time.time():.3f}".encode()


def replay(driver_ids: list[str], interval: float) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for lat, lng in TRACK:
            for driver_id in driver_ids:
                sock.sendto(encode_fix(driver_id, lat, lng), (LOCATION_HOST, LOCATION_PORT))
            time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--driver", action="append", default=None)
    parser.add_argument("--interval", type=float, default=0.2)
    args = parser.parse_args()
    replay(args.driver or ["d-1"], args.interval)


if __name__ == "__main__":
    main()
