#!/usr/bin/env bash
# Starts redpanda + provider + merchant + ledger, drives every link via the dashboard driver,
# and collects the RECV lines into observed.log.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
REDPANDA="tiny2-payhooks-redpanda"
KAFKA_PORT=46092
PROVIDER_PORT=46010
MERCHANT_PORT=46020
LEDGER_PORT=46030
PIDS=()

mkdir -p "$RUN"
rm -f "$RUN"/*.log "$ROOT/observed.log"

cleanup() {
  exec 2>/dev/null  # silence job-control "Terminated" notices during teardown
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  sleep 0.5
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && pkill -P "$pid" 2>/dev/null || true
    [ -n "$pid" ] && wait "$pid" 2>/dev/null || true
  done
  docker rm -f "$REDPANDA" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_http() { # url, name
  for _ in $(seq 1 120); do
    if curl -fsS "$1" >/dev/null 2>&1; then return 0; fi
    sleep 0.5
  done
  echo "timed out waiting for $2 ($1)" >&2
  exit 1
}

echo "== installing dependencies"
if [ ! -x "$ROOT/provider/.venv/bin/python" ]; then
  (cd "$ROOT/provider" && uv venv -q -p 3.13 .venv && uv pip install -q -p .venv/bin/python -r pyproject.toml)
fi
[ -d "$ROOT/merchant/node_modules" ] || (cd "$ROOT/merchant" && npm install --silent)
[ -d "$ROOT/dashboard/node_modules" ] || (cd "$ROOT/dashboard" && npm install --silent)
(cd "$ROOT/dashboard" && npx tsc -p .)
(cd "$ROOT/ledger" && cargo build --release --quiet)

echo "== starting redpanda"
docker rm -f "$REDPANDA" >/dev/null 2>&1 || true
docker run -d --name "$REDPANDA" -p "$KAFKA_PORT:$KAFKA_PORT" redpandadata/redpanda:v24.2.18 \
  redpanda start --mode dev-container --smp 1 --memory 512M --overprovisioned \
  --kafka-addr "internal://0.0.0.0:9092,external://0.0.0.0:$KAFKA_PORT" \
  --advertise-kafka-addr "internal://localhost:9092,external://127.0.0.1:$KAFKA_PORT" >/dev/null
for _ in $(seq 1 60); do
  if docker exec "$REDPANDA" rpk cluster health 2>/dev/null | grep -q 'Healthy:.*true'; then break; fi
  sleep 1
done
docker exec "$REDPANDA" rpk topic create payments.settled payments.refunded -p 1 >/dev/null

echo "== starting services"
(cd "$ROOT/ledger" && KAFKA_BROKERS="127.0.0.1:$KAFKA_PORT" LEDGER_PORT="$LEDGER_PORT" \
  exec ./target/release/ledger) >"$RUN/ledger.log" 2>&1 &
PIDS+=($!)
(cd "$ROOT/provider" && KAFKA_BROKERS="127.0.0.1:$KAFKA_PORT" \
  exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PROVIDER_PORT") >"$RUN/provider.log" 2>&1 &
PIDS+=($!)
wait_http "http://127.0.0.1:$LEDGER_PORT/healthz" ledger
wait_http "http://127.0.0.1:$PROVIDER_PORT/v1/healthz" provider

(cd "$ROOT/merchant" && PORT="$MERCHANT_PORT" PUBLIC_URL="http://127.0.0.1:$MERCHANT_PORT" \
  PROVIDER_URL="http://127.0.0.1:$PROVIDER_PORT" LEDGER_URL="http://127.0.0.1:$LEDGER_PORT" \
  exec node_modules/.bin/tsx src/server.ts) >"$RUN/merchant.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$MERCHANT_PORT/healthz" 2>/dev/null | grep -q '"registered":true'; then break; fi
  sleep 0.5
done

echo "== driving the dashboard"
(cd "$ROOT/dashboard" && MERCHANT_URL="http://127.0.0.1:$MERCHANT_PORT" \
  node_modules/.bin/tsx scripts/drive.ts) 2>&1 | tee "$RUN/dashboard.log"
sleep 1

grep -h 'RECV ' "$RUN"/*.log | sort -k2,2 -s >"$ROOT/observed.log" || true
echo "== observed links"
missing=0
for id in $(python3 -c 'import json,sys; print(" ".join(l["id"] for l in json.load(open(sys.argv[1]))["links"]))' "$ROOT/TRUTH.json"); do
  if grep -q "^RECV $id " "$ROOT/observed.log"; then echo "  $id ok"; else echo "  $id MISSING"; missing=1; fi
done
exit "$missing"
