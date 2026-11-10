#!/usr/bin/env bash
# Install deps, start redis + api + summarizer + web, drive every link once, collect RECV lines.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUN="$ROOT/.run"
API_PORT=41010
WEB_PORT=41020
REDIS_PORT=41079
REDIS_CTR=tiny2-newsroom-redis
API_URL="http://127.0.0.1:$API_PORT"

mkdir -p "$RUN"
rm -f "$RUN"/*.log
: > "$ROOT/observed.log"
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  docker rm -f "$REDIS_CTR" >/dev/null 2>&1 || true
  grep -h '^RECV ' "$RUN"/*.log 2>/dev/null | sort -u -k2,2 > "$ROOT/observed.log" || true
}
trap cleanup EXIT

wait_http() { # url, name
  for _ in $(seq 1 60); do
    curl -fsS -o /dev/null "$1" 2>/dev/null && return 0
    sleep 0.5
  done
  echo "$2 did not come up" >&2
  return 1
}

echo "== installing dependencies"
(cd "$ROOT/api" && { [ -d .venv ] || uv venv -q -p 3.13 .venv; } && uv pip install -q -p .venv/bin/python -r pyproject.toml)
(cd "$ROOT/web" && { [ -d node_modules ] || npm install --no-audit --no-fund --silent; })
(cd "$ROOT/summarizer" && cargo build --release -q)

echo "== starting redis ($REDIS_CTR on :$REDIS_PORT)"
docker rm -f "$REDIS_CTR" >/dev/null 2>&1 || true
docker run -d --rm --name "$REDIS_CTR" -p "127.0.0.1:$REDIS_PORT:6379" redis:7-alpine >/dev/null
for _ in $(seq 1 30); do
  docker exec "$REDIS_CTR" redis-cli ping 2>/dev/null | grep -q PONG && break
  sleep 0.5
done
export REDIS_URL="redis://127.0.0.1:$REDIS_PORT/0"

echo "== starting api on :$API_PORT"
(cd "$ROOT/api" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") > "$RUN/api.log" 2>&1 &
PIDS+=($!)

echo "== starting summarizer"
NEWSROOM_API_URL="$API_URL" "$ROOT/summarizer/target/release/newsroom-summarizer" > "$RUN/summarizer.log" 2>&1 &
PIDS+=($!)

echo "== building + serving web on :$WEB_PORT"
(cd "$ROOT/web" && npm run -s build)
(cd "$ROOT/web" && WEB_PORT="$WEB_PORT" exec node --import tsx server.ts) > "$RUN/web.log" 2>&1 &
PIDS+=($!)

wait_http "$API_URL/healthz" api
wait_http "http://127.0.0.1:$WEB_PORT/" web
# smoke check that the static page is served (driver only, not an app link)
curl -fsS "http://127.0.0.1:$WEB_PORT/" | grep -q 'newsroom-api'

echo "== driving the web client"
(cd "$ROOT/web" && NEWSROOM_API_URL="$API_URL" node --import tsx scripts/drive.ts) 2>&1 | tee "$RUN/drive.log"
sleep 1

echo "== checking links"
grep -h '^RECV ' "$RUN"/*.log | sort -u -k2,2 > "$ROOT/observed.log"
missing=0
for id in $(grep -o '"id": "[A-Z][0-9]*"' "$ROOT/TRUTH.json" | cut -d'"' -f4); do
  if ! grep -q "^RECV $id " "$ROOT/observed.log"; then
    echo "MISSING $id" >&2
    missing=1
  fi
done
cat "$ROOT/observed.log"
[ "$missing" -eq 0 ] && echo "== all links observed"
exit "$missing"
