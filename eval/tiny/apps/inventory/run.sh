#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=SC1091
source .env
set +a

RUN_DIR="$ROOT/.run"
rm -rf "$RUN_DIR" "$ROOT/observed.log"
mkdir -p "$RUN_DIR"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  docker compose -p tiny-inventory down -v --remove-orphans >/dev/null 2>&1 || true
  docker rm -f tiny-inventory-kafka >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_port() {
  local port="$1" name="$2"
  for _ in $(seq 1 60); do
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then return 0; fi
    sleep 0.5
  done
  echo "$name did not open port $port" >&2
  cat "$RUN_DIR/$name.log" >&2 || true
  return 1
}

echo "==> installing dependencies"
for svc in inventory purchasing; do
  [[ -x "$svc/.venv/bin/python" ]] || python3.13 -m venv "$svc/.venv"
  "$svc/.venv/bin/pip" install -q --disable-pip-version-check -r "$svc/requirements.txt"
done
(cd inventory && .venv/bin/python -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/inventory.proto)
(cd warehouse && npm install --silent --no-audit --no-fund)

echo "==> starting kafka"
KAFKA_OK=0
if docker compose -p tiny-inventory up -d kafka >"$RUN_DIR/docker.log" 2>&1; then
  for _ in $(seq 1 60); do
    if docker exec tiny-inventory-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 \
        --create --if-not-exists --topic "$STOCK_LOW_TOPIC" --partitions 1 --replication-factor 1 \
        >>"$RUN_DIR/docker.log" 2>&1; then
      KAFKA_OK=1
      break
    fi
    sleep 1
  done
fi
[[ "$KAFKA_OK" == 1 ]] && echo "    kafka ready" || echo "    kafka unavailable, skipping kafka flows"

echo "==> starting services"
(cd inventory && exec .venv/bin/python -u server.py) >"$RUN_DIR/inventory.log" 2>&1 &
PIDS+=($!)
wait_for_port "$INVENTORY_GRPC_PORT" inventory

(cd warehouse && PORT="$WAREHOUSE_PORT" exec node src/server.js) >"$RUN_DIR/warehouse.log" 2>&1 &
PIDS+=($!)
wait_for_port "$WAREHOUSE_PORT" warehouse

if [[ "$KAFKA_OK" == 1 ]]; then
  (cd purchasing && exec .venv/bin/python -u consumer.py) >"$RUN_DIR/purchasing.log" 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 60); do
    grep -q "purchasing consuming" "$RUN_DIR/purchasing.log" 2>/dev/null && break
    sleep 0.5
  done
fi

echo "==> exercising the app"
STATUS=0
WAREHOUSE_API_URL="http://127.0.0.1:$WAREHOUSE_PORT" WITH_KAFKA="$KAFKA_OK" \
  bash scripts/smoke.sh | tee "$RUN_DIR/smoke.log" || STATUS=$?
sleep 1

grep -ho 'RECV [^ ]* [^ ]* [^ ]*' "$RUN_DIR"/inventory.log "$RUN_DIR"/warehouse.log \
  "$RUN_DIR"/purchasing.log 2>/dev/null >"$ROOT/observed.log" || true

echo "==> observed messages"
sort "$ROOT/observed.log" | uniq -c
exit "$STATUS"
