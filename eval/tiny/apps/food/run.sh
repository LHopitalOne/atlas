#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$ROOT/logs"
RABBIT=tiny-food-rabbitmq
RESTAURANT_URL=http://127.0.0.1:41510
PIDS=()

mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$ROOT/observed.log"

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  docker rm -f "$RABBIT" >/dev/null 2>&1 || true
  cat "$LOGS"/*.log 2>/dev/null | grep -E '^RECV ' > "$ROOT/observed.log" || true
  echo "--- observed.log ---"
  cat "$ROOT/observed.log"
}
trap cleanup EXIT

echo "== installing dependencies"
for svc in restaurant courier; do
  [ -d "$ROOT/$svc/.venv" ] || python3.13 -m venv "$ROOT/$svc/.venv"
  "$ROOT/$svc/.venv/bin/pip" install -q -r "$ROOT/$svc/requirements.txt"
done
(cd "$ROOT/customer-web" && npm install --silent --no-audit --no-fund)

echo "== starting rabbitmq"
docker rm -f "$RABBIT" >/dev/null 2>&1 || true
BROKER=0
if docker run -d --name "$RABBIT" -p 127.0.0.1:41520:5672 rabbitmq:3.13-alpine >/dev/null 2>&1; then
  for _ in $(seq 1 60); do
    if docker logs "$RABBIT" 2>&1 | grep -q "Server startup complete"; then
      BROKER=1; break
    fi
    sleep 1
  done
fi
[ "$BROKER" = 1 ] && echo "rabbitmq up" || echo "rabbitmq unavailable: skipping amqp flows"

echo "== starting restaurant"
(cd "$ROOT/restaurant" && exec .venv/bin/python -m app.main) > "$LOGS/restaurant.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 40); do
  curl -fs "$RESTAURANT_URL/healthz" >/dev/null && break
  sleep 0.25
done

if [ "$BROKER" = 1 ]; then
  echo "== starting courier"
  (cd "$ROOT/courier" && exec .venv/bin/python -m courier.worker) > "$LOGS/courier.log" 2>&1 &
  PIDS+=($!)
  sleep 1
fi

echo "== customer places an order"
UNTIL=delivered
[ "$BROKER" = 1 ] || UNTIL=received
(cd "$ROOT/customer-web" && exec npx tsx --env-file=.env src/main.ts "$UNTIL") > "$LOGS/customer-web.out" 2>&1 &
CUSTOMER=$!
PIDS+=($CUSTOMER)

ORDER_ID=""
for _ in $(seq 1 60); do
  ORDER_ID=$(sed -n 's/^placed order \([0-9]*\)$/\1/p' "$LOGS/customer-web.out" | head -1)
  [ -n "$ORDER_ID" ] && break
  sleep 0.25
done
[ -n "$ORDER_ID" ] || { cat "$LOGS/customer-web.out"; exit 1; }

if [ "$BROKER" = 1 ]; then
  echo "== kitchen marks order $ORDER_ID ready"
  curl -fs -X POST "$RESTAURANT_URL/orders/$ORDER_ID/ready" >/dev/null
fi

wait "$CUSTOMER"
cat "$LOGS/customer-web.out"
echo "== all flows done"
