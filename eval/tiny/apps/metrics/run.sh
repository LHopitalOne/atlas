#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$ROOT/observed.log"

set -a
source "$ROOT/.env"
set +a

echo "==> installing dependencies"
if [ ! -x "$ROOT/collector/.venv/bin/python" ]; then
  python3.13 -m venv "$ROOT/collector/.venv"
fi
"$ROOT/collector/.venv/bin/pip" install -q -r "$ROOT/collector/requirements.txt"
(cd "$ROOT/agent" && cargo build -q)
(cd "$ROOT/dashboard" && npm install --silent && npm run -s build)

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

echo "==> starting collector"
(cd "$ROOT/collector" && exec .venv/bin/python -m collector) >"$LOGS/collector.log" 2>&1 &
PIDS+=($!)

for _ in $(seq 1 50); do
  curl -sf "$COLLECTOR_URL/healthz" >/dev/null 2>&1 && break
  sleep 0.2
done

echo "==> running agent (tcp line protocol + udp statsd)"
AGENT_ITERATIONS=3 AGENT_INTERVAL_MS=200 "$ROOT/agent/target/debug/agent" >"$LOGS/agent.log" 2>&1

echo "==> running dashboard (http api)"
(cd "$ROOT/dashboard" && node dist/index.js --once) >"$LOGS/dashboard.log" 2>&1
cat "$LOGS/dashboard.log"

sleep 0.5
cleanup
PIDS=()

grep -ho 'RECV .*' "$LOGS"/*.log | sort | uniq -c | sort -rn
grep -ho 'RECV .*' "$LOGS"/*.log > "$ROOT/observed.log"

missing=0
for expected in \
  "RECV tcp SEND tcp:41710" \
  "RECV udp SEND udp:41711" \
  "RECV http GET /healthz" \
  "RECV http GET /api/metrics" \
  "RECV http GET /api/metrics/{name}" \
  "RECV http GET /api/metrics/{name}/summary" \
  "RECV http POST /api/annotations"; do
  if ! grep -qxF "$expected" "$ROOT/observed.log"; then
    echo "MISSING: $expected"
    missing=1
  fi
done
[ "$missing" -eq 0 ] && echo "==> all communications observed"
exit "$missing"
