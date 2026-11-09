#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$ROOT/.run"
API_PORT=41810
PAYMENTS_PORT=41820
PIDS=()

rm -rf "$LOGS" && mkdir -p "$LOGS"

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

set -a
source "$ROOT/.env"
set +a

wait_for() {
  local url="$1"
  for _ in $(seq 1 60); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  echo "timed out waiting for $url" >&2
  return 1
}

echo "==> installing dependencies"
for svc in booking-api payments; do
  [ -x "$ROOT/$svc/.venv/bin/python" ] || python3.13 -m venv "$ROOT/$svc/.venv"
  "$ROOT/$svc/.venv/bin/pip" install -q --disable-pip-version-check -r "$ROOT/$svc/requirements.txt"
done
(cd "$ROOT/booking-web" && npm install --no-audit --no-fund --silent)

echo "==> starting services"
(cd "$ROOT/payments" && exec .venv/bin/gunicorn --bind "127.0.0.1:$PAYMENTS_PORT" --workers 1 --threads 4 "app:create_app()") \
  >"$LOGS/payments.log" 2>&1 &
PIDS+=($!)
(cd "$ROOT/booking-api" && BOOKING_PAYMENTS_URL="http://127.0.0.1:$PAYMENTS_PORT" \
  exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") \
  >"$LOGS/booking-api.log" 2>&1 &
PIDS+=($!)

wait_for "http://127.0.0.1:$PAYMENTS_PORT/health"
wait_for "http://127.0.0.1:$API_PORT/healthz"

echo "==> exercising booking-web -> booking-api -> payments"
(cd "$ROOT/booking-web" && VITE_API_URL="http://127.0.0.1:$API_PORT" npm run --silent smoke)

sleep 0.5
cleanup
PIDS=()

grep -hoE 'RECV [a-z]+ [^ ]+ [^ ]+' "$LOGS"/*.log > "$ROOT/observed.log" || true
echo "==> observed.log"
cat "$ROOT/observed.log"
