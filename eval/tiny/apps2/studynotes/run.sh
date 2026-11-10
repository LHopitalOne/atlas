#!/usr/bin/env bash
# Starts every studynotes service, exercises every link once, collects RECV lines into observed.log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.run"
mkdir -p "$RUN"
rm -f "$RUN"/*.log "$ROOT/observed.log"

export TRPC_PORT=45010
export GRAPHQL_PORT=45011
export INDEXER_LISTEN=127.0.0.1:45020
export INDEXER_ADDR=127.0.0.1:45020
export NOTES_API_URL=http://127.0.0.1:45010
export NOTES_GRAPHQL_URL=http://127.0.0.1:45011/graphql

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_port() {
  local port=$1 name=$2
  for _ in $(seq 1 100); do
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then return 0; fi
    sleep 0.2
  done
  echo "timeout waiting for $name on :$port" >&2
  cat "$RUN/$name.log" >&2 || true
  exit 1
}

echo "== install"
(cd "$ROOT/indexer" && cargo build --release --quiet)
(cd "$ROOT/notes-server" && [[ -d node_modules ]] || npm install --no-audit --no-fund --silent)
(cd "$ROOT/notes-web" && [[ -d node_modules ]] || npm install --no-audit --no-fund --silent)
(cd "$ROOT/reminder-cron" && { [[ -d .venv ]] || uv venv -q -p 3.13 .venv; } && uv pip install -q -p .venv/bin/python httpx)

echo "== start"
"$ROOT/indexer/target/release/indexer" >"$RUN/indexer.log" 2>&1 &
PIDS+=($!)
wait_port 45020 indexer

(cd "$ROOT/notes-server" && exec node_modules/.bin/tsx src/index.ts) >"$RUN/notes-server.log" 2>&1 &
PIDS+=($!)
wait_port 45010 notes-server
wait_port 45011 notes-server

echo "== exercise"
(cd "$ROOT/notes-web" && node_modules/.bin/tsx src/main.ts) 2>&1 | tee "$RUN/notes-web.log"
(cd "$ROOT/reminder-cron" && .venv/bin/python -m reminder_cron --once) 2>&1 | tee "$RUN/reminder-cron.log"
sleep 0.5

echo "== collect"
grep -h '^RECV ' "$RUN"/*.log | sort -u -k2,2 >"$ROOT/observed.log" || true
cat "$ROOT/observed.log"
EXPECTED=$(python3 -c 'import json,sys; print(" ".join(l["id"] for l in json.load(open(sys.argv[1]))["links"]))' "$ROOT/TRUTH.json" 2>/dev/null || true)
missing=0
for id in $EXPECTED; do
  grep -q "^RECV $id " "$ROOT/observed.log" || { echo "MISSING $id"; missing=1; }
done
[[ $missing -eq 0 ]] && echo "all links observed"
exit $missing
