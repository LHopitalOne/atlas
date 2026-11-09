# Tiny apps: every kind of link, checked by running

Ten small multi-service apps (a shop, an HR tool, a taxi app, a chat, a payments ledger, food delivery, a notes app,
a metrics pipeline, a booking app, inventory) in `apps/`, written by agents that never saw the link finder, in the
languages it reads (Python, JavaScript/TypeScript, Rust). Each has a `TRUTH.json` of its links and a `run.sh` that
installs, starts every service, exercises every link and records what each receiver logged. A second agent per app
read the code independently, ran it and corrected the truth: every one of the 73 links was observed at run time.

| Protocol | Links |
| --- | --- |
| HTTP | 50 |
| WebSocket | 6 |
| GraphQL | 5 |
| gRPC | 5 |
| Kafka | 2 |
| UDP | 2 |
| RabbitMQ | 1 |
| Redis pub/sub | 1 |
| TCP | 1 |

They are small enough to run in under five minutes each, so a change to the finder is measured in seconds, on every
protocol, against links known to happen.

```bash
python3 eval/tiny/run.py eval/tiny/apps /tmp/tiny-out --python bridge/.venv/bin/python
```

`run.py` treats each service folder as a repository, gives no aliases (a first try, as on code never seen) and links
a service's frontend to its own backend (`--within`); `score.py` matches each truth link by its receiving end (the
same file within 2 lines, or the same channel) for every protocol.

## Results

| Finder | Links found | False links | HTTP | Other protocols |
| --- | --- | --- | --- | --- |
| Before (commit `1f9a1ff`) | 18 / 73 | 0 | 18 / 50 | 0 / 23 |
| JavaScript wrappers followed, TypeScript generic calls, decorators never requests | 34 / 73 | 0 | 34 / 50 | 0 / 23 |
| Channel catalog per language (Kafka, RabbitMQ, Redis, gRPC, WebSocket, TCP/UDP, GraphQL), Next.js file routes, SWR, config objects | **64 / 73** | **0** | 43 / 50 | 21 / 23 |

The channel catalog is one table of library entry points per language (which call sends or receives, on which
protocol, which argument is the channel) over shared machinery that traces a receiver to the library that made it and
resolves the channel value. Each language's table was reviewed by a second agent whose only job was to reject rules
tied to these apps rather than to a library's documented API; the reviewers removed several (gRPC servicer methods
that are not handlers, GraphQL roots found by class name, ports a test passes). The four real projects did not change
(Sentry 20/20, Open edX 61/71, Label Studio 6/15, Mozilla 0/41, 0 false links).

Still missed: the six ledger links go through a client SDK, which `--library` follows only with SCIP indexes (this
run builds none); two are a WebSocket server pushing to a client on a socket it accepted (no channel names that
direction); one is an HTTP call.

These apps are now a development set: the rules were written while looking at their misses. They show that the
approach covers every protocol, not how well it does on code never seen; that is measured on held-out projects.

## What the misses said

Before any change, every missed link was diagnosed (by an agent that saw the code, the truth and what the finder
extracted, not the finder's code) and the diagnosis checked by a second one:

- In 48 of the 55 misses the sending call was never extracted; in the other 7 it was, with the wrong channel. The
  receiving side was found correctly for 26 of them.
- The channel's words appear in the sender's code for 69 of the 73 links and somewhere in both services for 67; at
  the receiving declaration itself only for 22, because receivers assemble it (prefix mounts, routers, schemas,
  config).
- Pairing equal channel-like strings across services, with no library knowledge at all, touches 38 of the 73 links,
  but with no direction or line and with pairs between services that never talk: a signal, not a detector.

| What a miss needed | Links |
| --- | --- |
| Following the channel through helpers, class fields, options objects, config objects (language-level) | 33 |
| A sending library the reader does not know (WebSocket, Kafka, RabbitMQ, Redis, gRPC, sockets) | 18 |
| A receiving library the reader does not know | 18 |
| A client library (SDK) between caller and request | 6 |
| Receivers assembled by framework structure (Next.js file routes, prefix mounts) | 6 |
| A shared schema (`.proto`, GraphQL with name transforms) | 5 |
