#!/usr/bin/env bash
# Local smoke run: install deps, start every service, drive one shopping flow, stop.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
set -a; source .env; set +a

RUN_DIR="$ROOT/.run"
REDIS_CONTAINER=tiny-shop-redis
GATEWAY="http://127.0.0.1:${GATEWAY_PORT}"
PIDS=()

rm -rf "$RUN_DIR"; mkdir -p "$RUN_DIR"
rm -f "$ROOT/observed.log"

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
  grep -ho 'RECV .*' "$RUN_DIR"/*.log > "$ROOT/observed.log" 2>/dev/null || true
}
trap cleanup EXIT

wait_for_port() {
  local port=$1 name=$2
  for _ in $(seq 1 100); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then return 0; fi
    sleep 0.2
  done
  echo "$name did not open port $port" >&2
  return 1
}

wait_for_line() {
  local file=$1 pattern=$2
  for _ in $(seq 1 100); do
    grep -q "$pattern" "$file" 2>/dev/null && return 0
    sleep 0.2
  done
  echo "timed out waiting for '$pattern' in $file" >&2
  return 1
}

echo "==> installing dependencies"
for svc in catalog orders notifier; do
  [ -x "$svc/.venv/bin/python" ] || python3.13 -m venv "$svc/.venv"
  "$svc/.venv/bin/pip" install -q --disable-pip-version-check -r "$svc/requirements.txt"
done
(cd gateway && npm install --silent --no-audit --no-fund)

echo "==> starting redis"
REDIS_OK=1
docker rm -f "$REDIS_CONTAINER" >/dev/null 2>&1 || true
if docker run -d --name "$REDIS_CONTAINER" -p "127.0.0.1:${REDIS_PORT}:6379" redis:7-alpine >/dev/null 2>&1 \
   && wait_for_port "$REDIS_PORT" redis; then
  for _ in $(seq 1 50); do
    docker exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null | grep -q PONG && break
    sleep 0.2
  done
else
  REDIS_OK=0
  echo "redis unavailable: skipping notifier and the order-event flow" >&2
fi

echo "==> starting services"
export PYTHONUNBUFFERED=1
(cd catalog && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$CATALOG_PORT") > "$RUN_DIR/catalog.log" 2>&1 &
PIDS+=($!)
(cd orders && exec .venv/bin/python wsgi.py) > "$RUN_DIR/orders.log" 2>&1 &
PIDS+=($!)
if [ "$REDIS_OK" = 1 ]; then
  (cd notifier && exec .venv/bin/python -m notifier) > "$RUN_DIR/notifier.log" 2>&1 &
  PIDS+=($!)
fi
(cd gateway && exec node src/server.js) > "$RUN_DIR/gateway.log" 2>&1 &
PIDS+=($!)

wait_for_port "$CATALOG_PORT" catalog
wait_for_port "$ORDERS_PORT" orders
wait_for_port "$GATEWAY_PORT" gateway
[ "$REDIS_OK" = 1 ] && wait_for_line "$RUN_DIR/notifier.log" "subscribed to"

echo "==> driving the shop through the gateway"
call() {
  local method=$1 path=$2 body=${3:-}
  echo "--- $method $path"
  if [ -n "$body" ]; then
    curl -fsS -X "$method" -H 'content-type: application/json' -d "$body" "$GATEWAY$path"
  else
    curl -fsS -X "$method" "$GATEWAY$path"
  fi
  echo
}

call GET  /api/products
call GET  /api/products/2
call POST /api/orders '{"email":"ana@example.com","items":[{"product_id":1,"quantity":2},{"product_id":4,"quantity":1}]}'
call GET  /api/orders/1

if [ "$REDIS_OK" = 1 ]; then
  wait_for_line "$RUN_DIR/notifier.log" "RECV redis"
fi

cleanup
trap - EXIT

echo "==> observed.log"
cat "$ROOT/observed.log"
