#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGS="$ROOT/logs"
mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$ROOT/observed.log"

set -a
source "$ROOT/.env"
set +a

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT

wait_port() {
  local port=$1
  for _ in $(seq 1 100); do
    if (exec 3<>/dev/tcp/127.0.0.1/"$port") 2>/dev/null; then return 0; fi
    sleep 0.2
  done
  echo "port $port did not open" >&2
  return 1
}

echo "== installing moderation"
cd "$ROOT/moderation"
[ -x .venv/bin/python ] || python3.13 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m grpc_tools.protoc -Iapp/pb=protos --python_out=. --grpc_python_out=. protos/moderation.proto

echo "== installing chat-server"
cd "$ROOT/chat-server"
npm install --silent --no-audit --no-fund

echo "== installing + building web"
cd "$ROOT/web"
npm install --silent --no-audit --no-fund
npm run --silent build

echo "== starting services"
cd "$ROOT/moderation"
PYTHONUNBUFFERED=1 .venv/bin/python -m app.server > "$LOGS/moderation.log" 2>&1 &
PIDS+=($!)
wait_port "$MODERATION_GRPC_PORT"

cd "$ROOT/chat-server"
PORT="$CHAT_PORT" MODERATION_ADDR="127.0.0.1:$MODERATION_GRPC_PORT" node src/index.js > "$LOGS/chat-server.log" 2>&1 &
PIDS+=($!)
wait_port "$CHAT_PORT"

echo "== exercising flows"
cd "$ROOT"
node scripts/smoke.mjs > "$LOGS/web.log" 2>&1 || { cat "$LOGS"/*.log; exit 1; }
cat "$LOGS/web.log" | grep '^smoke:' || true
sleep 0.5

cleanup
PIDS=()

grep -h '^RECV ' "$LOGS"/*.log > "$ROOT/observed.log" || true
echo "== observed"
sort "$ROOT/observed.log" | uniq -c
