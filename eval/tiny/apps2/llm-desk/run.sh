#!/usr/bin/env bash
# Installs, starts and exercises every llm-desk link, then writes observed.log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.run"
REDIS_CONTAINER=tiny2-llmdesk-redis
REDIS_PORT=42079
DESK_PORT=42000
REDIS_URL="redis://127.0.0.1:${REDIS_PORT}/0"

: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY must be set}"

mkdir -p "$RUN"
rm -f "$RUN"/*.log
: > "$ROOT/observed.log"
PIDS=()

cleanup() {
  local pid
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill -TERM "$pid" 2>/dev/null || true
  done
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && wait "$pid" 2>/dev/null || true
  done
  docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  grep -h '^RECV ' "$RUN"/*.log > "$ROOT/observed.log" 2>/dev/null || true
}
trap cleanup EXIT

wait_for() { # wait_for <seconds> <description> <command...>
  local secs=$1 what=$2; shift 2
  for _ in $(seq "$secs"); do
    if "$@" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  echo "timed out waiting for $what" >&2
  return 1
}

echo "== installing dependencies"
(cd "$ROOT/desk" && { [[ -x .venv/bin/python ]] || uv venv -q -p 3.13 .venv; } && uv pip install -q -p .venv/bin/python -r pyproject.toml)
(cd "$ROOT/agent-console" && npm install --silent --no-audit --no-fund)
(cd "$ROOT/analytics" && npm install --silent --no-audit --no-fund)

echo "== starting redis ($REDIS_CONTAINER on :$REDIS_PORT)"
docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
docker run -d --rm --name "$REDIS_CONTAINER" -p "127.0.0.1:${REDIS_PORT}:6379" redis:7-alpine >/dev/null
wait_for 30 redis docker exec "$REDIS_CONTAINER" redis-cli ping

echo "== starting desk on :$DESK_PORT"
(cd "$ROOT/desk" && PYTHONUNBUFFERED=1 DESK_PORT=$DESK_PORT DESK_REDIS_URL="$REDIS_URL" \
  exec .venv/bin/python -m desk.main) > "$RUN/desk.log" 2>&1 &
PIDS+=($!)
wait_for 60 desk curl -fsS "http://127.0.0.1:${DESK_PORT}/healthz"

echo "== starting analytics"
(cd "$ROOT/analytics" && REDIS_URL="$REDIS_URL" FLUSH_INTERVAL_MS=2000 \
  exec node --import tsx src/index.ts) > "$RUN/analytics.log" 2>&1 &
ANALYTICS_PID=$!
PIDS+=($ANALYTICS_PID)
wait_for 30 analytics grep -q 'analytics consuming' "$RUN/analytics.log"

echo "== agent-console shift"
(cd "$ROOT/agent-console" && DESK_URL="http://127.0.0.1:${DESK_PORT}" AGENT_NAME=dana \
  node --import tsx src/cli.ts shift fixtures/tickets.json) 2>&1 | tee "$RUN/agent-console.log"

echo "== waiting for analytics report"
wait_for 60 'analytics report' grep -q '^RECV O3 ' "$RUN/analytics.log"

cleanup
trap - EXIT

echo "== observed links"
sort -u -k2,2 "$ROOT/observed.log" | awk '{print $2}' | sort | tr '\n' ' '; echo
missing=0
for id in $(python3 -c 'import json,sys; print(" ".join(l["id"] for l in json.load(open(sys.argv[1]))["links"]))' "$ROOT/TRUTH.json"); do
  if ! grep -q "^RECV $id " "$ROOT/observed.log"; then echo "MISSING $id"; missing=1; fi
done
[[ $missing -eq 0 ]] && echo "all TRUTH.json links observed"
exit $missing
