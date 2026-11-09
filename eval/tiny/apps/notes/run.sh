#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$ROOT/.logs"
mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$ROOT/observed.log"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && pkill -P "$pid" 2>/dev/null || true
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_port() {
  for _ in $(seq 1 120); do
    nc -z 127.0.0.1 "$1" 2>/dev/null && return 0
    sleep 0.5
  done
  echo "port $1 did not open" >&2
  return 1
}

echo "== installing dependencies"
(cd "$ROOT/search-indexer" && { [ -x .venv/bin/python ] || python3.13 -m venv .venv; } && .venv/bin/pip install -q -r requirements.txt)
(cd "$ROOT/notes-web" && npm install --no-audit --no-fund --silent)

echo "== starting search-indexer"
(cd "$ROOT/search-indexer" && SEARCH_PORT=41602 exec .venv/bin/python -m app.main) >"$LOGS/search-indexer.log" 2>&1 &
PIDS+=($!)

echo "== starting notes-web"
rm -rf "$ROOT/notes-web/data"
(cd "$ROOT/notes-web" && SEARCH_INDEXER_URL=http://127.0.0.1:41602 exec npx next dev -H 127.0.0.1 -p 41601) >"$LOGS/notes-web.log" 2>&1 &
PIDS+=($!)

wait_port 41602
wait_port 41601

echo "== driving"
node "$ROOT/notes-web/scripts/smoke.mjs"
sleep 1

cleanup
trap - EXIT

grep -h '^RECV ' "$LOGS"/*.log > "$ROOT/observed.log"
echo "== observed"
sort "$ROOT/observed.log" | uniq -c
