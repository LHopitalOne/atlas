#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
set -a; source .env; set +a
export PIP_DISABLE_PIP_VERSION_CHECK=1

LOGS="$ROOT/logs"
rm -rf "$LOGS"; mkdir -p "$LOGS"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  cat "$LOGS"/*.log 2>/dev/null | grep -E '^RECV ' > "$ROOT/observed.log" || true
  echo "--- observed.log ---"
  cat "$ROOT/observed.log"
}
trap cleanup EXIT

wait_for() {
  local file="$1" pattern="$2" timeout="${3:-30}"
  for _ in $(seq $((timeout * 10))); do
    grep -q "$pattern" "$file" 2>/dev/null && return 0
    sleep 0.1
  done
  echo "timeout waiting for '$pattern' in $file" >&2
  cat "$file" >&2 || true
  return 1
}

echo "==> installing dependencies"
(cd dispatch && npm install --silent --no-audit --no-fund)
(cd driver-app && npm install --silent --no-audit --no-fund && npm run build --silent)
for svc in location gps-simulator; do
  [ -x "$svc/.venv/bin/python" ] || python3.13 -m venv "$svc/.venv"
  "$svc/.venv/bin/pip" install -q -r "$svc/requirements.txt"
done

echo "==> starting services"
(cd dispatch && exec node src/index.js) > "$LOGS/dispatch.log" 2>&1 &
PIDS+=($!)
wait_for "$LOGS/dispatch.log" "dispatch listening"

(cd location && exec .venv/bin/python -u -m location_service) > "$LOGS/location.log" 2>&1 &
PIDS+=($!)
wait_for "$LOGS/location.log" "location listening"

(cd driver-app && EXIT_AFTER_PICKUP=1 exec node dist/index.js) > "$LOGS/driver-app.log" 2>&1 &
DRIVER_PID=$!
PIDS+=($DRIVER_PID)
wait_for "$LOGS/dispatch.log" "RECV websocket SEND /drivers/stream"

echo "==> rider requests a ride"
curl -sf -X POST "http://127.0.0.1:${DISPATCH_PORT}/rides" \
  -H 'content-type: application/json' \
  -d '{"riderId":"r-42","pickup":{"lat":40.7458,"lng":-73.985},"dropoff":{"lat":40.758,"lng":-73.9855}}'
echo
wait_for "$LOGS/driver-app.log" "is accepted"

echo "==> replaying GPS track"
(cd gps-simulator && .venv/bin/python simulate.py --driver "$DRIVER_ID" --interval 0.2) > "$LOGS/gps-simulator.log" 2>&1
wait_for "$LOGS/driver-app.log" "approaching pickup"

for _ in $(seq 50); do kill -0 "$DRIVER_PID" 2>/dev/null || break; sleep 0.1; done

echo "==> done"
