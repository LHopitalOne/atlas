# payhooks

A payments sandbox: a fake payment provider settles card payments, notifies the merchant through a signed
webhook sent to a URL the merchant registered at run time, and publishes settlement events to Kafka (Redpanda)
for a ledger. The merchant streams order status to browsers over Server-Sent Events.

## Services

| service | folder | stack | port |
|---|---|---|---|
| provider | `provider/` | Python 3.13, FastAPI, httpx, aiokafka | 46010 |
| merchant | `merchant/` | TypeScript, Fastify 5, axios, global fetch (run with tsx) | 46020 |
| dashboard | `dashboard/` | browser TypeScript (EventSource + fetch); `scripts/drive.ts` runs the same module in Node with the `eventsource` package | - |
| ledger | `ledger/` | Rust, rskafka consumer + axum HTTP API | 46030 |
| redpanda | docker `tiny2-payhooks-redpanda` | Kafka API | 46092 |

Flow: merchant starts and POSTs its webhook URL to the provider -> the dashboard places an order -> the merchant
checks the card BIN at binlist (falls back to httpbin when binlist says no), creates a provider payment -> the provider
settles it in a background task, publishes `payments.settled` and POSTs a signed `payment.settled` webhook to the stored
URL -> the merchant pushes the new status down the SSE stream -> the dashboard refunds; same path with
`payments.refunded` -> the dashboard asks the merchant for the balance, which the merchant reads from the ledger.

## Links (14)

| id | protocol | caller -> target | operation | channel |
|---|---|---|---|---|
| L01 | http | merchant -> provider | POST | /v1/merchants |
| L02 | http | merchant -> provider | POST | /v1/payments |
| L03 | http | merchant -> provider | POST | /v1/payments/{payment_id}/refunds |
| L04 | http (webhook) | provider -> merchant | POST | /webhooks/payhooks |
| L05 | kafka | provider -> ledger | PUBLISH | payments.settled |
| L06 | kafka | provider -> ledger | PUBLISH | payments.refunded |
| L07 | http | merchant -> ledger | GET | /balances/{merchant_id} |
| L08 | sse | dashboard -> merchant | GET | /api/orders/:orderId/events |
| L09 | http | dashboard -> merchant | POST | /api/orders |
| L10 | http | dashboard -> merchant | POST | /api/orders/:orderId/refund |
| L11 | http | dashboard -> merchant | GET | /api/balance |
| L12 | http | merchant -> outside lookup.binlist.net | GET | /{bin} |
| L13 | http | merchant -> outside httpbin.org | GET | /anything/bins/{bin} |
| L14 | http | dashboard -> outside www.githubstatus.com | LINK | / (`<a href>` in index.html) |

By protocol: http 10 (7 internal, 3 outside), sse 1, kafka 2. Exact send/receive lines are in `TRUTH.json`.

## Idioms tested

- Webhook whose URL never appears in the sender: the provider stores `webhook_url` from the registration body and
  later calls `httpx.AsyncClient.post(merchant.webhook_url, ...)` from a FastAPI `BackgroundTasks` job (L04).
- Generic fetch wrapper `providerPost(path, body)` using `new URL(path, config.providerUrl)` with env base URL (L01-L03).
- axios instance with `baseURL` from env (L07); axum 0.8 `{param}` route on the receiver.
- aiokafka `send_and_wait(topic, ...)` behind per-event methods and a topic constants module; rskafka partition
  clients wrapped in a `subscribe()` helper, two streams merged with `futures::stream::select` (L05, L06).
- Fastify plugins mounted with `prefix` (`/api`, `/webhooks`); SSE via `reply.hijack()` + `reply.raw.write` (L08).
- Browser module whose base URL comes from `configure()` and an `apiUrl()` helper; the same module is driven from Node
  by assigning the `eventsource` package to `globalThis.EventSource` (L08-L11).
- Outside calls with module-level base constants and template literals, including a fallback branch (L12, L13);
  an `<a href>` to another site (L14).

## Running

`./run.sh` installs dependencies (uv, npm, cargo), starts Redpanda in docker plus the three services, runs the
dashboard driver (`dashboard/scripts/drive.ts`), collects every `RECV <id>` line into `observed.log`, checks that every
link in `TRUTH.json` was seen, and tears everything down. About 20 seconds once dependencies are built.
