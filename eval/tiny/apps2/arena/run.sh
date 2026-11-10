#!/usr/bin/env bash
# Installs deps, starts all arena services, plays one game, collects RECV lines into observed.log.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN="$ROOT/.run"
mkdir -p "$RUN"
rm -f "$RUN"/*.log "$ROOT/observed.log"

GAME_PORT=44010
SCORE_UDP_PORT=44020
SCORE_HTTP_PORT=44021
PIDS=()

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait_pid() {
  local pid="$1" deadline=$((SECONDS + $2))
  while kill -0 "$pid" 2>/dev/null; do
    if (( SECONDS >= deadline )); then
      kill "$pid" 2>/dev/null || true
      return 1
    fi
    sleep 0.5
  done
  wait "$pid"
}

wait_http() {
  local url="$1"
  for _ in $(seq 1 60); do
    curl -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 0.5
  done
  echo "timed out waiting for $url" >&2
  return 1
}

echo "== installing dependencies"
(cd "$ROOT/game-server" && npm install --silent --no-audit --no-fund)
(cd "$ROOT/player-web" && npm install --silent --no-audit --no-fund && npm run -s build)
(cd "$ROOT/quiz-bot" && { [[ -d .venv ]] || uv venv -q --python 3.13 .venv; } && uv pip install -q --python .venv/bin/python -e .)
(cd "$ROOT/scorekeeper" && cargo build --release --quiet)

echo "== starting scorekeeper"
SCOREKEEPER_UDP_ADDR="127.0.0.1:$SCORE_UDP_PORT" SCOREKEEPER_HTTP_ADDR="127.0.0.1:$SCORE_HTTP_PORT" \
  "$ROOT/scorekeeper/target/release/scorekeeper" >"$RUN/scorekeeper.log" 2>&1 &
PIDS+=($!)

echo "== starting game-server"
(cd "$ROOT/game-server" && PORT=$GAME_PORT \
  SCOREKEEPER_URL="http://127.0.0.1:$SCORE_HTTP_PORT" \
  SCOREKEEPER_UDP_HOST=127.0.0.1 SCOREKEEPER_UDP_PORT=$SCORE_UDP_PORT \
  exec node_modules/.bin/tsx src/server.ts) >"$RUN/game-server.log" 2>&1 &
PIDS+=($!)

wait_http "http://127.0.0.1:$SCORE_HTTP_PORT/healthz"
wait_http "http://127.0.0.1:$GAME_PORT/healthz"

echo "== player-web: checking external assets referenced by index.html"
(cd "$ROOT/player-web" && node_modules/.bin/tsx scripts/check-assets.ts) >"$RUN/assets.log" 2>&1 || true
# The page itself is the caller for these HTML links; record them on its behalf.
{
  grep -E '^ASSET 2[0-9][0-9] https://fonts\.googleapis\.com/css2' "$RUN/assets.log" | sed 's/^/RECV O02 player-web /' || true
  grep -E '^ASSET 2[0-9][0-9] https://opentdb\.com/' "$RUN/assets.log" | sed 's/^/RECV O03 player-web /' || true
} >"$RUN/player-web-html.log"

echo "== starting quiz-bot (seeds from Open Trivia DB, then joins)"
(cd "$ROOT/quiz-bot" && GAME_SERVER_URL="http://127.0.0.1:$GAME_PORT" ROOM=arena-1 \
  exec .venv/bin/python -u -m quiz_bot) >"$RUN/quiz-bot.log" 2>&1 &
BOT_PID=$!
PIDS+=($BOT_PID)

echo "== playing as player-web"
(cd "$ROOT/player-web" && GAME_SERVER_URL="http://127.0.0.1:$GAME_PORT" ROOM=arena-1 PLAYER_NAME=alice \
  exec node_modules/.bin/tsx scripts/play.ts) >"$RUN/player-web.log" 2>&1 &
PLAYER_PID=$!
PIDS+=($PLAYER_PID)

wait_pid "$PLAYER_PID" 120 || echo "player-web driver failed or timed out" >&2
wait_pid "$BOT_PID" 30 || echo "quiz-bot failed or timed out" >&2
sleep 0.5

grep -h 'RECV ' "$RUN"/*.log | sed -E 's/^.*(RECV )/\1/' >"$ROOT/observed.log" || true

echo "== observed link ids"
grep -oE '^RECV [A-Z][0-9]+' "$ROOT/observed.log" | sort | uniq -c

missing=0
for id in $(grep -oE '"id": "[A-Z][0-9]+"' "$ROOT/TRUTH.json" | grep -oE '[A-Z][0-9]+'); do
  if ! grep -qE "^RECV $id " "$ROOT/observed.log"; then
    echo "MISSING $id" >&2
    missing=1
  fi
done
[[ $missing -eq 0 ]] && echo "== all TRUTH links observed"
exit $missing
