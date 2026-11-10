# arena

A small real-time multiplayer trivia quiz. Players join a room on a Socket.IO namespace, get questions pushed
to them, answer, and see round results; scores are streamed to a separate scorekeeper over UDP and the
leaderboard is read back over HTTP. Questions come from the public Open Trivia DB.

## Services

| service | language | what it does | port |
|---|---|---|---|
| `game-server` | TypeScript (express + socket.io) | `/quiz` namespace with rooms; REST `POST /admin/questions`, `GET /api/leaderboard` | 44010 |
| `player-web` | TypeScript (socket.io-client) | browser client (`index.html`, `src/main.ts`) built on the `QuizClient` wrapper; `scripts/play.ts` drives the same wrapper from Node | - |
| `quiz-bot` | Python 3.13 (python-socketio AsyncClient, httpx) | fetches trivia from opentdb.com, seeds the game-server, then plays via a class-based namespace | - |
| `scorekeeper` | Rust (std UdpSocket + tiny_http) | UDP score updates on 44020, `GET /scores` on 44021 | 44020/udp, 44021 |

## Links (15)

| id | protocol | caller -> target | op | channel |
|---|---|---|---|---|
| A01 | websocket | player-web -> game-server | EMIT | /quiz:join |
| A02 | websocket | player-web -> game-server | EMIT | /quiz:answer |
| A03 | websocket | game-server -> player-web | EMIT | /quiz:question |
| A04 | websocket | game-server -> player-web | EMIT | /quiz:round_result |
| A05 | websocket | quiz-bot -> game-server | EMIT | /quiz:join |
| A06 | websocket | quiz-bot -> game-server | EMIT | /quiz:answer |
| A07 | websocket | game-server -> quiz-bot | EMIT | /quiz:question |
| A08 | websocket | game-server -> quiz-bot | EMIT | /quiz:round_result |
| H01 | http | quiz-bot -> game-server | POST | /admin/questions |
| H02 | http | player-web -> game-server | GET | /api/leaderboard |
| H03 | http | game-server -> scorekeeper | GET | /scores |
| U01 | udp | game-server -> scorekeeper | SEND | 44020 |
| O01 | http | quiz-bot -> opentdb.com | GET | /api.php |
| O02 | http | player-web (index.html) -> fonts.googleapis.com | GET | /css2 |
| O03 | http | player-web (index.html) -> opentdb.com | LINK | / |

By protocol: websocket 8, http 6 (3 internal, 3 outside), udp 1.

## Idioms tested

- Socket.IO event names live in a shared constants object (`QuizEvents`) and the namespace in `QUIZ_NAMESPACE`;
  nothing at the emit/listen sites is a string literal.
- Client emits go through a generic private `send(event, payload)` in a wrapper class; the namespace is appended
  to the base URL in `io(...)`.
- Server pushes go through a room broadcast helper: `this.nsp.to(roomId).emit(event, payload)` with `nsp = io.of('/quiz')`
  injected into the room class.
- Python bot uses a class-based `socketio.AsyncClientNamespace` subclass: handlers are `on_question` /
  `on_round_result` methods (event name only implied by the method name) and emits use a `StrEnum` member.
- HTTP: httpx `AsyncClient(base_url=...)` + relative path; native `fetch` with template literal and with
  `new URL(path, base)`; express `Router` mounted under `/admin` and `/api`; Rust tiny_http `match (method, url)`.
- UDP: `node:dgram` socket in a reporter class, host/port from config; Rust `UdpSocket::bind` + `recv_from` loop.
- Outside: module-level URL constant with `params=` (opentdb), Google Fonts `<link href>`, attribution `<a href>`.

## Running

`./run.sh` installs dependencies, starts scorekeeper and game-server, runs the asset check for index.html, starts
the bot and the headless player, plays one 3-question game, and writes every `RECV <id>` line to `observed.log`.
The HTML links (O02, O03) are observed by `scripts/check-assets.ts`, which fetches each external URL in
`index.html`; run.sh tags those results with the link ids.
