"""Exercise billing end to end (which drives ledger through ledger-sdk)."""
import os
import sys

import requests

BILLING = os.environ.get("BILLING_URL", "http://127.0.0.1:41411")


def check(resp, status=200):
    if resp.status_code != status:
        sys.exit(f"{resp.request.method} {resp.url} -> {resp.status_code} {resp.text}")
    return resp.json()


def main():
    print("healthz", check(requests.get(f"{BILLING}/healthz")))
    customer = check(requests.post(f"{BILLING}/customers", json={"email": "ada@example.com"}), 201)
    cid = customer["id"]
    print("customer", check(requests.get(f"{BILLING}/customers/{cid}")))
    print("charge", check(requests.post(f"{BILLING}/customers/{cid}/charges", json={"amount_cents": 1999}), 201))
    print("charge", check(requests.post(f"{BILLING}/customers/{cid}/charges", json={"amount_cents": 500, "invoice_id": "inv_manual"}), 201))
    print("charges", check(requests.get(f"{BILLING}/customers/{cid}/charges")))
    print("balance", check(requests.get(f"{BILLING}/customers/{cid}/balance")))


if __name__ == "__main__":
    main()
