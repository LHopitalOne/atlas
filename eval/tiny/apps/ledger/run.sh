#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$ROOT/.logs"
mkdir -p "$LOGS"
: > "$ROOT/observed.log"

export LEDGER_HOST=127.0.0.1 LEDGER_PORT=41410
export LEDGER_URL="http://127.0.0.1:41410"
BILLING_PORT=41411

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_for() {
  local url="$1"
  for _ in $(seq 1 100); do
    curl -fs "$url" >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  echo "timed out waiting for $url" >&2
  return 1
}

echo "==> building ledger"
(cd "$ROOT/ledger" && cargo build --release --quiet)

echo "==> installing billing (with ledger-sdk)"
if [ ! -x "$ROOT/billing/.venv/bin/python" ]; then
  python3.13 -m venv "$ROOT/billing/.venv"
fi
(cd "$ROOT/billing" && .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt requests)

echo "==> starting services"
"$ROOT/ledger/target/release/ledger" > "$LOGS/ledger.log" 2>&1 &
PIDS+=($!)
(cd "$ROOT/billing" && exec .venv/bin/gunicorn -w 1 -b "127.0.0.1:$BILLING_PORT" wsgi:app) > "$LOGS/billing.log" 2>&1 &
PIDS+=($!)

wait_for "http://127.0.0.1:41410/health"
wait_for "http://127.0.0.1:$BILLING_PORT/healthz"

echo "==> driving"
BILLING_URL="http://127.0.0.1:$BILLING_PORT" "$ROOT/billing/.venv/bin/python" "$ROOT/scripts/drive.py"

sleep 0.5
cleanup
PIDS=()

grep -ho 'RECV .*' "$LOGS/ledger.log" "$LOGS/billing.log" > "$ROOT/observed.log" || true
echo "==> observed.log"
sort "$ROOT/observed.log" | uniq -c
