# Atlas

A zoomable map of a codebase or a service graph: repositories, domains, services and endpoints, and the contracts between them.
Google Maps-style navigation, labels and directions; WebGL2 rendering that stays smooth at 100,000 nodes.
Builds to a single HTML file. By default it shows its own source code, indexed with tree-sitter and SCIP.

## Quick start

```bash
npm install
npm run build                       # dist/atlas.html, dist/atlas-offline.html
open dist/atlas-offline.html
```

Show your own graph: `node scripts/build.mjs --offline --graph=my-graph.json` (format: docs/GRAPH_SPEC.md),
or call `window.Atlas.loadGraph(spec)` in the page.

## Graphify graphs on the map

[Graphify](https://github.com/Graphify-Labs/graphify) turns a repository into `graphify-out/graph.json`.
`bridge/` (Python 3.10+, no dependencies) draws one or more of those on Atlas:

```bash
graphify update path/to/repo                                   # writes path/to/repo/graphify-out/graph.json
python3 -m atlas_bridge spec path/to/repo/graphify-out/graph.json -o graph.json   # run from bridge/
node scripts/build.mjs --offline --graph=bridge/graph.json
```

Files become services, functions and classes become leaves, Graphify's communities become domains
(`--group folder` uses folders instead), and Graphify's EXTRACTED / INFERRED / AMBIGUOUS tags become Atlas's link
colours. Pass several graphs (`api=a/graph.json web=b/graph.json`), or one built with `graphify merge-graphs`, and
each repository gets its own territory.

## HTTP links between repositories

Graphify maps each repository on its own; `graphify merge-graphs` puts several side by side. `links` finds the HTTP
requests one repository sends to routes another serves, and adds them as edges:

```bash
pip install './bridge[links]'                       # tree-sitter and its Python, Rust, JavaScript grammars
graphify merge-graphs api/graphify-out/graph.json web/graphify-out/graph.json --out merged.json
python3 -m atlas_bridge links api web --graph merged.json --graphify-out merged-links.json -o links.json
graphify path "placeOrder()" "POST /orders" --graph merged-links.json   # Graphify now crosses repositories
python3 -m atlas_bridge spec merged-links.json -o graph.json             # and so does the Atlas map
```

It reads routes (Django URLconfs with includes, DRF routers and their `@action`s, plugin URL configs, Flask and
FastAPI decorators, axum and actix routers, Express) and requests (urllib3, requests, httpx, reqwest, fetch, axios,
and request types that declare their own path). It follows URLs through wrapper functions back to the literal path,
through helpers that return a URL (`getBookmarksBaseUrl()`, `self._make_url(path)`), URL objects (`new URL(...).href`),
`urljoin`, and Django settings (`settings.LMS_API_URLS['blocks']`).

The target service comes from names near the request (`_snuba_pool`, `SymbolicatorSession`, `--alias
upstream=sentry`) and from where configuration says services live. Settings modules, `.env` files and docker-compose
files name URLs (`COURSE_CATALOG_API_URL = 'http://edx.devstack.discovery:18381/api/v1'`,
`LMS_BASE_URL='http://localhost:18000'`, a compose service publishing `18381:18381`), so a request to
`localhost:18381`, `10.0.0.5:18381`, a Docker DNS name or a configured setting reaches the service that address
belongs to. `localhost` and bare IPs only count with their port; an address two services claim counts for neither.
When a base URL carries part of the path, a route behind a short API prefix (`/api/v1`) fits, preferring the prefix
configuration names, then one the base URL's name mentions (`lms_coursemode_api_url` -> `/api/course_modes/v1`).

Each link says how sure it is: **matched** (a named service, one route fits), **inferred** (no name, a route behind a
prefix the base URL is assumed to carry, or a URL made absolute and handed to another service to fetch),
**ambiguous** (several routes fit) or **unmatched** (the named service has no such route). Requests made only by
tests are left out unless `--include-tests`.

### Confirming links with SCIP

A link rests on names the finder resolved without a compiler: the client a request goes through
(`_snuba_pool` here is the pool defined at `snuba.py:590`), each wrapper call it followed back to the literal path,
the request trait a Rust type implements. [SCIP](https://github.com/sourcegraph/scip) indexes record where every name
really points, so they can check those guesses:

```bash
python3 -m atlas_bridge index sentry relay snuba symbolicator -o scip      # scip-python, rust-analyzer, scip-typescript
python3 -m atlas_bridge links sentry relay snuba symbolicator --alias upstream=sentry --scip-dir scip -o links.json
```

Each matched link is then **confirmed** (every name it rests on resolves where the finder assumed), **syntax** (it
rests on no name lookup: read straight from the code), **contradicted** (a name resolves elsewhere) or **unverified**.
The indexers never run the repositories' code: scip-python and scip-typescript only type-check, and rust-analyzer runs
with build scripts and procedural macros switched off. SCIP files are read without a protobuf dependency. What no
index can confirm is configuration: which host a base URL points to when the code runs.

Without the repository's libraries installed, an index cannot say where a call into them goes (`requests`, Django, a
client SDK). `index --sandbox` (needs Docker) indexes Python in a throwaway container instead: the repository is
mounted read-only, the libraries it declares (requirements files, `pyproject.toml`, Poetry) are installed there,
where install scripts can do no harm, and only the index is written back. On Label Studio this takes the libraries
the index resolves from none to 55.

Services often talk through a client library that lives in a repository of its own (an SDK): the service calls
`ls.tasks.get(id)` and the HTTP request is built inside the SDK. `links --library sdk=folder` reads the library too,
and, with SCIP indexes of every repository, walks from each request the library sends up through the library's own
functions to the service lines that call into it, where the request is reported. Each call followed is an assumption
the indexes check, across repositories: `model.py:291 -> TasksClient.get -> RawTasksClient.get -> GET /api/tasks/{id}/`.

```bash
python3 -m atlas_bridge index --sandbox -o scip label-studio label-studio-ml-backend label-studio-sdk
python3 -m atlas_bridge links label-studio label-studio-ml-backend --library label-studio-sdk --scip-dir scip -o links.json
```

Most products keep their frontend and backend in one repository. `links --within` also links browser code to its own
repository's server routes: a request to a relative path goes to the origin that served the page. It needs every
fixed word of the path to meet a route's (a catch-all page route never takes it), and a generic helper that requests
`/api/0/{anything}` is linked only when one route fits. On Sentry alone that is 225 frontend-to-backend links, on
Label Studio 9; these have no answer key yet, so they are not in the scores above.

`eval/sentry/` and `eval/openedx/` are answer keys of the real links between four Sentry services and four Open edX
ones (the second built after the finder was tuned on the first, to test whether it generalises);
`eval/labelstudio/` is a held-out key the frozen finder was run on once. `eval/score.py` scores a run:

```bash
python3 -m atlas_bridge links sentry relay snuba symbolicator --alias upstream=sentry -o links.json
python3 eval/score.py eval/sentry/answer-key.json links.json
```

| | Sentry | Open edX | Label Studio (held out) |
| --- | --- | --- | --- |
| Production links found | 20 / 20 | 61 / 71 (12 / 71 before the held-out fixes) | 6 / 15 (3 / 15 frozen; 4 / 4 sent by the services' own code, 2 / 11 sent through the SDK, traced with `--library`) |
| False links | 0 | 0 (31 before) | 0 |

`eval/score.py` once credited a key link when a found link's route sat within 3 lines of it, even when that found link
was another key link's route; it no longer does, which took Open edX from 68 to 61 (the finder sends Discovery's list
requests to the detail route, and five catalog links had been credited for a neighbouring course route).

The bridge follows the dependency rule of clean architecture; `lint-imports` enforces it:

| Ring | Module | May import |
| --- | --- | --- |
| Entities | `core/model.py`: files, symbols, links, link certainty | the standard library, no I/O |
| Entities | `core/http.py`: path templates, routes, requests, how well a request fits a route | the standard library, no I/O |
| Entities | `core/addresses.py`: service URLs configuration names, hosts and ports | the standard library, no I/O |
| Use cases | `usecases/draw.py`: arrange a code graph as repos > domains > files | `core` |
| Use cases | `usecases/link.py`: match requests to other repositories' routes; the `Extractor` port | `core` |
| Use cases | `usecases/addresses.py`, `usecases/bases.py`: which service an address or setting points at, which prefix a base URL carries | `core` |
| Adapters | `adapters/graphify.py` (graph.json in and out), `adapters/atlas.py` (Atlas spec out), `adapters/treesitter/` (routes and requests from source), `adapters/linkfile.py` (links JSON) | `usecases`, `core`; never each other |
| Driver | `__main__.py`: command line, files, wiring | everything |

```bash
cd bridge && pip install -r requirements-dev.txt
ruff check . && ruff format --check . && lint-imports
coverage run -m unittest discover -s tests -t . && coverage report      # fails under 75%
ATLAS_INTEGRATION=1 python -m unittest discover -s tests/integration -t .  # real Graphify, pinned version
```

### Code rules (Python)

`bridge/tests/test_architecture.py` and ruff enforce them in CI:

- `__init__.py` files only import and export (a docstring, imports, `__all__`).
- Modules stay under 300 lines, classes under 250, functions under 50, cyclomatic complexity at most 10.
- Object-oriented: abstract bases with concrete subclasses (`Command`, `Presenter`, `Grouping`, `LinkRule`,
  `LanguageExtractor`, `Workspace`, `RouteCollector`, `CallCollector`, `ValueResolver`, `TestPathPolicy`), state kept
  private behind methods.
- Every error is a subclass of `BridgeError` from `core/errors.py`; the command line turns them into a message and
  an exit code (2 for input the user can fix).
- Every regex is a named, compiled, commented constant; nothing calls `re.sub(r'...')` inline.

## Continuous integration

`.github/workflows/ci.yml` runs on every push to `master` and every pull request:

| Job | Checks |
| --- | --- |
| JS lint and import rules | ESLint, Prettier, the layer rules in `test/architecture.test.js` |
| JS unit tests | Node's test runner; fails under 75% line, branch or function coverage |
| Bridge | Ruff lint and format, import-linter contracts, unit tests; fails under 75% coverage |
| Integration | Real Graphify on `bridge/tests/fixtures/shop`, through the bridge, into Atlas's validator, equal to the golden spec |
| E2E | Playwright on the built page, including a Graphify graph drawn from the golden spec |

Licence: Apache-2.0.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run build` | Bundle `src/` with esbuild into the two single-file pages |
| `npm test` | Unit and architecture tests (Node's test runner) |
| `npm run test:coverage` | Unit tests with 75% line, branch and function coverage gates |
| `npm run lint:imports` | The layer rules only (`test/architecture.test.js`) |
| `npm run test:e2e` | Browser tests with Playwright (set `CHROMIUM_PATH` to use a specific Chromium) |
| `npm run lint` | ESLint |
| `npm run check` | Lint, import rules, unit tests with coverage, build, end-to-end tests |
| `npm run index:self` | Re-index Atlas's own code into `generated/self-graph.json` |

## Layout

```
src/
  main.js            entry: support check, init order, boot, Atlas.loadGraph
  state.js config.js dom.js index.html
  util/              math, format (pure), dom (browser)
  model/ graph/      generation, spec validation, layout, indexes, route search (pure, Node-testable)
  render/            WebGL2 layers, frame loop, overlay, labels, minimap
  app/               camera, focus, selection, routes, URL, keyboard and pointer input
  ask/               questions about the code: shared lookup tools, offline answers, Claude engine
  ui/                panels: inspector, directions, search, key, needs attention, ask, controls
test/                unit + architecture tests; test/e2e/ Playwright
tools/index-self/    tree-sitter + SCIP indexer for the Self graph
docs/                DECISIONS, ARCHITECTURE, GRAPH_SPEC, INTEGRATION
bridge/              Python: Graphify graph.json to Atlas (core, usecases, adapters, CLI)
eval/sentry/         answer key: verified HTTP links between Sentry's repos, for scoring the link finder
eval/openedx/, eval/labelstudio/  more answer keys, built without the finder (see each README)
```

See `CLAUDE.md` for the rules the code follows.
