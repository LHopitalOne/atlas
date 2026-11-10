# Tiny apps, second set: harder idioms and outside services

Six more multi-service apps, built by agents that never saw the link finder, with idioms the first set does not have.
Each app's `run.sh` starts every service and exercises every link; all 80 links were observed at run time.
`TRUTH.json` also lists requests to outside hosts (`"target": "outside"`, with `"host"`), which `score.py` matches
against the finder's outside-service links.

| App | What it tests | Links |
| --- | --- | --- |
| newsroom | OpenAPI-generated TS client (`@hey-api/openapi-ts`), FastAPI router prefixes, Redis list + pub/sub, Rust worker calling back, Hacker News API, Google Fonts | 12 |
| llm-desk | Jev on OpenRouter via httpx `base_url`, the `openai` SDK (no path in the call), a typed client class, SSE, Redis streams, httpbin | 10 |
| gateway | Express gateway with `http-proxy-middleware` path rewrites, axios `baseURL: '/api'`, axum nested routers, Flask blueprints, open.er-api.com, unpkg | 15 |
| arena | Socket.IO namespaces and events, python-socketio bot, Node `dgram` UDP to a Rust service, Open Trivia DB | 15 |
| studynotes | tRPC v11 (batched), GraphQL (graphql-yoga), gRPC (grpc-js to tonic), tsconfig path alias, httpx calling tRPC directly | 14 |
| payhooks | webhooks to a URL registered at run time, Kafka (Redpanda, rskafka), SSE, axios + fetch, binlist and httpbin | 14 |

```bash
python3 eval/tiny/run.py eval/tiny/apps2 /tmp/apps2-out --python bridge/.venv/bin/python [-- --jev]
```

## First score (finder frozen before the apps were written; no tuning on them)

| App | Found | False links |
| --- | --- | --- |
| gateway | 14 / 15 | 0 |
| payhooks | 8 / 14 | 0 |
| llm-desk | 5 / 10 | 0 |
| arena | 3 / 15 | 0 |
| newsroom | 2 / 12 | 0 |
| studynotes | 0 / 14 | 0 |
| **All** | **32 / 80** | **0** |

llm-desk was 0 / 10 before one general fix made while reading it (a FastAPI router created inside the app factory
function, `api = APIRouter(prefix='/api')` in `create_app()`, now gives its prefix). `--jev` adds nothing here: the
misses are requests the finder does not read at all (Socket.IO events, tRPC procedure proxies, generated clients'
option objects, SDK calls), and Jev only chooses among routes for requests that were read.
