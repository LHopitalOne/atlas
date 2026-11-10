# llm-desk

A support desk that triages incoming tickets with an LLM. Customers' tickets are filed through a REST API,
Jev (TypeSafe `typesafe/jev-1.14` on OpenRouter) decides whether each ticket is urgent and which team owns it,
a small chat model drafts the first reply, and an analytics worker counts triaged tickets per day and team.

## Services

| service | folder | stack | role |
|---|---|---|---|
| desk | `desk/` | Python 3.13, FastAPI, httpx, openai SDK, redis.asyncio | REST API (`/api/tickets...`), SSE feed (`/api/events/stream`), Jev triage, reply drafting, XADD to `desk.tickets.triaged` |
| agent-console | `agent-console/` | TypeScript (Node, tsx) | CLI for support agents: typed `DeskClient` class for the REST API + `LiveFeed` SSE subscription |
| analytics | `analytics/` | TypeScript (Node, tsx), ioredis | XREADGROUP consumer of the triaged stream; POSTs daily counts to httpbin.org |

Ports: desk on 42000, Redis container `tiny2-llmdesk-redis` on 42079.

## Links (10)

| id | protocol | caller -> target | operation | channel |
|---|---|---|---|---|
| H1 | http | agent-console -> desk | POST | /api/tickets |
| H2 | http | agent-console -> desk | GET | /api/tickets |
| H3 | http | agent-console -> desk | GET | /api/tickets/{ticket_id} |
| H4 | http | agent-console -> desk | POST | /api/tickets/{ticket_id}/reply |
| H5 | http | agent-console -> desk | PATCH | /api/tickets/{ticket_id} |
| S1 | http (SSE) | agent-console -> desk | GET | /api/events/stream |
| R1 | redis stream | desk -> analytics | PUBLISH (XADD / XREADGROUP) | desk.tickets.triaged |
| O1 | http | desk -> openrouter.ai (outside) | POST | /api/alpha/decisions |
| O2 | http | desk -> openrouter.ai (outside) | POST | /api/v1/chat/completions |
| O3 | http | analytics -> httpbin.org (outside) | POST | /post |

By protocol: HTTP between services 6 (5 REST + 1 SSE), Redis stream 1, outside HTTP 3. `TRUTH.json` is the answer key.

## Idioms tested

- **Typed client class**: `DeskClient` keeps the base URL in a private field (from `DESK_URL` via a config module),
  each method builds a literal or template path and delegates to one generic `send()` that calls `fetch(this.baseUrl + path)`.
  The HTTP method is a string argument of `send()`, so GET/POST/PATCH are only visible at the method call sites.
- **Nested FastAPI routers**: receiver paths are `APIRouter(prefix="/api")` + `APIRouter(prefix="/tickets")` + route path
  (`""`, `"/{ticket_id}"`, `"/{ticket_id}/reply"`).
- **SSE over fetch streaming**: the URL comes from `new URL('/api/events/stream', this.baseUrl)`, is passed to a
  `LiveFeed` class constructor, and fetched in `open()`; the server side is a `StreamingResponse` with `text/event-stream`.
- **Redis stream**: `redis.asyncio` `xadd(self._stream, ...)` with the stream name from pydantic-settings; consumed with ioredis
  `xreadgroup('GROUP', ..., 'STREAMS', this.cfg.stream, '>')` with the name from an env-backed config loader.
- **Outside link via httpx base_url**: `httpx.AsyncClient(base_url=settings.openrouter_url)` + `post(DECISIONS_PATH)` (module constant),
  invoked from a FastAPI `BackgroundTasks` task.
- **Outside link through an SDK**: `AsyncOpenAI(base_url="https://openrouter.ai/api/v1")` + `chat.completions.create(...)`; the
  path `/chat/completions` never appears in the source.
- **Outside link with full URL in config**: analytics `fetch(this.endpoint, {method: 'POST'})` where the endpoint is the
  `REPORT_URL` default `https://httpbin.org/post`.

## Running

`./run.sh` installs dependencies (uv + npm), starts Redis in Docker, desk and analytics, runs an agent-console
"shift" (3 tickets filed, triaged, the urgent one answered with a drafted reply and closed), waits for the analytics
report, stops everything and writes every `RECV <id>` line to `observed.log`. It uses 4 OpenRouter calls per run
(3 Jev decisions, 1 chat completion) and needs `OPENROUTER_API_KEY` in the environment.
