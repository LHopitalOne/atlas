# studynotes

A small study-notes app built on RPC styles: a tRPC v11 API with a GraphQL search endpoint, a TypeScript
client, a Python reminder job that speaks tRPC's HTTP wire format by hand, and a Rust gRPC full-text indexer.
It is the answer key for a static cross-service link finder; `TRUTH.json` lists every link.

## Services

| service | folder | stack | port |
|---|---|---|---|
| notes-server | `notes-server/` | Node/TS, tRPC v11 standalone adapter (`basePath: '/trpc/'`), graphql-yoga, @grpc/grpc-js client | 45010 (tRPC), 45011 (`/graphql`) |
| notes-web | `notes-web/` | Node/TS, `@trpc/client` (createTRPCClient + httpBatchLink), graphql-request, tsconfig alias `@/*` | - (CLI session `src/main.ts`) |
| reminder-cron | `reminder-cron/` | Python 3.13, httpx | - (`python -m reminder_cron [--once]`) |
| indexer | `indexer/` | Rust, tonic 0.14 + prost (protox instead of protoc) | 45020 |

`./run.sh` builds/installs, starts indexer + notes-server, runs one notes-web study session and one reminder sweep,
and writes the `RECV <id>` lines to `observed.log`. No docker containers are used.

## Links

| protocol | id | caller -> target | operation | channel |
|---|---|---|---|---|
| http (tRPC) | T01 | notes-web -> notes-server | MUTATION | /trpc/notes.create |
| http (tRPC) | T02 | notes-web -> notes-server | QUERY | /trpc/notes.list |
| http (tRPC) | T03 | notes-web -> notes-server | QUERY | /trpc/notes.byId |
| http (tRPC) | T04 | notes-web -> notes-server | MUTATION | /trpc/notes.delete |
| http (tRPC) | T05 | notes-web -> notes-server | QUERY | /trpc/tags.list |
| http (tRPC) | T06 | notes-web -> notes-server | MUTATION | /trpc/tags.attach |
| graphql | T07 | notes-web -> notes-server | QUERY | searchNotes |
| graphql | T08 | notes-web -> notes-server | MUTATION | saveSearch |
| http (tRPC wire) | T09 | reminder-cron -> notes-server | QUERY | /trpc/notes.due |
| http (tRPC wire) | T10 | reminder-cron -> notes-server | MUTATION | /trpc/notes.markReminded |
| http (outside) | T11 | reminder-cron -> httpbin.org | POST | /anything/email |
| grpc | T12 | notes-server -> indexer | CALL | studynotes.indexer.v1.Indexer/IndexNote |
| grpc | T13 | notes-server -> indexer | CALL | studynotes.indexer.v1.Indexer/Search |
| grpc | T14 | notes-server -> indexer | CALL | studynotes.indexer.v1.Indexer/RemoveNote |

Totals:

- http: 9 (T01-T06, T09, T10 are tRPC procedures; T11 is the outside host httpbin.org)
- graphql: 2 (T07, T08)
- grpc: 3 (T12-T14)

## Idioms tested

- tRPC procedure paths that never appear as strings on the client: `trpc.notes.create.mutate(...)` is a proxy
  property chain; the URL is `` httpBatchLink({ url: `${env.apiUrl}/trpc` }) `` and the receiver path is the
  standalone `basePath` + `appRouter` key + nested router key.
- httpBatchLink batching: `notes.list` and `tags.list` are fired in one `Promise.all`, so the wire request is
  `GET /trpc/notes.list,tags.list?batch=1`.
- Path alias imports (`@/lib/trpc`, `@/config`) via tsconfig `paths`, and a type-only `AppRouter` import from the
  server repo (not a link).
- Procedures declared as object keys of `router({...})` with chained `publicProcedure.input(...).query/mutation`.
- GraphQL: `graphql-request` client singleton with named operations in `gql` constants; graphql-yoga resolver map.
- Python calling tRPC without a tRPC client: `httpx.Client(base_url=f"{url}/trpc")` + relative `"/notes.due"` with
  `?input=<json>`, and POST with a raw JSON body for the mutation.
- Outside URL held as an env default in a dataclass, passed through constructors into `self._url`.
- gRPC via `@grpc/proto-loader` dynamic client; method names passed as strings to a generic `unary()` helper
  (`client[method](...)`) plus one direct callback call; tonic service trait impl on the Rust side.
- GraphQL resolver that itself makes a gRPC call (T07 -> T13), tRPC mutation that makes gRPC calls (T01 -> T12, T04 -> T14).
