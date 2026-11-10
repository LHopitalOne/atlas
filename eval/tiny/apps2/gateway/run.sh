#!/usr/bin/env bash
# Installs deps, starts users (Rust), orders (Flask), edge (Express gateway), drives the SPA api module
# through the gateway, and collects every `RECV <link id>` line into observed.log.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
mkdir -p "$RUN"
: > "$RUN/users.log"
: > "$RUN/orders.log"
: > "$RUN/edge.log"
: > "$RUN/spa.log"

export USERS_PORT=43020 ORDERS_PORT=43030 EDGE_PORT=43010
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "== installing dependencies"
(cd "$ROOT/users" && cargo build --release --quiet)
(cd "$ROOT/orders" && { [ -d .venv ] || uv venv -q --python 3.13 .venv; } && uv pip install -q --python .venv/bin/python -r pyproject.toml)
(cd "$ROOT/edge" && npm install --silent --no-audit --no-fund)
(cd "$ROOT/spa" && npm install --silent --no-audit --no-fund)

echo "== starting services"
(cd "$ROOT/users" && PORT=$USERS_PORT exec ./target/release/users) > "$RUN/users.log" 2>&1 &
PIDS+=($!)
(cd "$ROOT/orders" && PORT=$ORDERS_PORT USERS_SERVICE_URL="http://127.0.0.1:$USERS_PORT" exec .venv/bin/python main.py) > "$RUN/orders.log" 2>&1 &
PIDS+=($!)
(cd "$ROOT/edge" && PORT=$EDGE_PORT USERS_URL="http://127.0.0.1:$USERS_PORT" ORDERS_URL="http://127.0.0.1:$ORDERS_PORT" exec node_modules/.bin/tsx src/server.ts) > "$RUN/edge.log" 2>&1 &
PIDS+=($!)

wait_for() {
  local url="$1"
  for _ in $(seq 1 100); do
    curl -s -o /dev/null "$url" && return 0
    sleep 0.2
  done
  echo "timed out waiting for $url" >&2
  return 1
}
# readiness probes hit "/" (unrouted, 404) so they never look like a real link
wait_for "http://127.0.0.1:$USERS_PORT/"
wait_for "http://127.0.0.1:$ORDERS_PORT/"
wait_for "http://127.0.0.1:$EDGE_PORT/healthz"

echo "== driving the SPA api module through the gateway"
(cd "$ROOT/spa" && GATEWAY_ORIGIN="http://127.0.0.1:$EDGE_PORT" node_modules/.bin/tsx scripts/drive.ts) | tee "$RUN/spa.log"

sleep 0.5
{
  cat "$RUN/users.log" "$RUN/orders.log" "$RUN/edge.log" "$RUN/spa.log"
} | grep -E '^RECV ' | sort -k2,2 -s > "$ROOT/observed.log"

echo "== observed.log"
cat "$ROOT/observed.log"

missing=0
for id in $(grep -oE '"id": "[A-Z][0-9]+"' "$ROOT/TRUTH.json" | grep -oE '[A-Z][0-9]+'); do
  if ! grep -q "^RECV $id " "$ROOT/observed.log"; then
    echo "MISSING $id"
    missing=1
  fi
done
[ "$missing" -eq 0 ] && echo "== all links observed"
exit "$missing"
