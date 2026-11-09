#!/usr/bin/env bash
# Install, start, exercise and stop the whole HR app. Writes RECV lines to observed.log.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
set -a; source .env; set +a

RUN_DIR="$ROOT/.run"
rm -rf "$RUN_DIR" && mkdir -p "$RUN_DIR"
PIDS=()
KAFKA_OK=0

log() { echo "[run.sh] $*"; }

cleanup() {
  log "stopping services"
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null
  done
  sleep 1
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null
  done
  docker compose down -v --remove-orphans >/dev/null 2>&1
  docker rm -f tiny-hr-kafka >/dev/null 2>&1
  cat "$RUN_DIR"/*.log 2>/dev/null | grep -o 'RECV .*' > "$ROOT/observed.log"
  log "observed.log:"
  sort "$ROOT/observed.log" | uniq -c
}
trap cleanup EXIT

wait_port() {  # host port seconds
  local i
  for ((i = 0; i < $3 * 2; i++)); do
    (echo > "/dev/tcp/$1/$2") 2>/dev/null && return 0
    sleep 0.5
  done
  return 1
}

log "installing dependencies"
for svc in hr-app payroll; do
  [ -x "$svc/.venv/bin/python" ] || python3.13 -m venv "$svc/.venv"
  "$svc/.venv/bin/pip" install -q --disable-pip-version-check -r "$svc/requirements.txt" || exit 1
done
(cd hr-app/frontend && npm install --no-audit --no-fund --silent) || exit 1

log "starting kafka"
docker rm -f tiny-hr-kafka >/dev/null 2>&1
if docker compose up -d kafka >"$RUN_DIR/docker.out" 2>&1; then
  for _ in $(seq 1 60); do
    if docker exec tiny-hr-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 \
        --create --if-not-exists --topic "$EMPLOYEE_HIRED_TOPIC" --partitions 1 --replication-factor 1 >/dev/null 2>&1; then
      KAFKA_OK=1
      break
    fi
    sleep 1
  done
fi
if [ "$KAFKA_OK" = 1 ]; then log "kafka ready"; else log "kafka unavailable: skipping kafka flows"; fi

log "starting hr-app backend on :$HR_API_PORT"
rm -f hr-app/db.sqlite3
(cd hr-app && .venv/bin/python manage.py migrate -v 0 && .venv/bin/python manage.py loaddata -v 0 departments) || exit 1
(cd hr-app && exec .venv/bin/python -u manage.py runserver "127.0.0.1:$HR_API_PORT" --noreload) >"$RUN_DIR/hr-app.log" 2>&1 &
PIDS+=($!)
wait_port 127.0.0.1 "$HR_API_PORT" 30 || { log "backend did not start"; cat "$RUN_DIR/hr-app.log"; exit 1; }

log "starting hr-app frontend dev server on :$HR_WEB_PORT"
(cd hr-app/frontend && exec node_modules/.bin/vite) >"$RUN_DIR/frontend.log" 2>&1 &
PIDS+=($!)
wait_port 127.0.0.1 "$HR_WEB_PORT" 30 || { log "vite did not start"; cat "$RUN_DIR/frontend.log"; exit 1; }

if [ "$KAFKA_OK" = 1 ]; then
  log "starting payroll consumer"
  (cd payroll && exec .venv/bin/python -u -m payroll) >"$RUN_DIR/payroll.log" 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 20); do grep -q "payroll consuming" "$RUN_DIR/payroll.log" && break; sleep 0.5; done
fi

log "driving the frontend API client"
HR_WEB_ORIGIN="http://127.0.0.1:$HR_WEB_PORT" hr-app/frontend/node_modules/.bin/tsx driver/smoke.ts || STATUS=1

if [ "$KAFKA_OK" = 1 ]; then
  log "waiting for payroll to enroll the new hire"
  for _ in $(seq 1 60); do grep -q "enrolled employee" "$RUN_DIR/payroll.log" && break; sleep 0.5; done
  grep "enrolled employee" "$RUN_DIR/payroll.log" || { log "payroll did not process the event"; STATUS=1; }
fi

exit "${STATUS:-0}"
