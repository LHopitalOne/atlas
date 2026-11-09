#!/usr/bin/env bash
# End-to-end smoke test against a locally running stack.
set -euo pipefail

API="${WAREHOUSE_API_URL:-http://127.0.0.1:41975}"
WITH_KAFKA="${WITH_KAFKA:-1}"

json_field() { python3.13 -c "import json,sys; print(json.load(sys.stdin)[sys.argv[1]])" "$1"; }

echo "== stock level"
curl -fsS "$API/stock/SKU-1002"; echo

echo "== pick that keeps stock healthy, then cancel it"
pick=$(curl -fsS -X POST "$API/picks" -H 'content-type: application/json' \
  -d '{"sku":"SKU-1002","quantity":3,"orderId":"ord-100"}')
echo "$pick"
pick_id=$(echo "$pick" | json_field pickId)
curl -fsS -X DELETE "$API/picks/$pick_id"; echo

echo "== pick that drops SKU-1001 below the threshold"
curl -fsS -X POST "$API/picks" -H 'content-type: application/json' \
  -d '{"sku":"SKU-1001","quantity":8,"orderId":"ord-101"}'; echo

if [[ "$WITH_KAFKA" != "1" ]]; then
  echo "== kafka unavailable, skipping restock check"
  exit 0
fi

echo "== waiting for purchasing to place a restock order"
for _ in $(seq 1 60); do
  orders=$(curl -fsS "$API/restock-orders")
  if [[ "$orders" != "[]" ]]; then
    echo "$orders"
    exit 0
  fi
  sleep 0.5
done
echo "no restock order placed" >&2
exit 1
