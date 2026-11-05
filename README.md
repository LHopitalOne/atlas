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

The bridge follows the dependency rule of clean architecture; `lint-imports` enforces it:

| Ring | Module | May import |
| --- | --- | --- |
| Entities | `core/model.py`: files, symbols, links, link certainty | the standard library, no I/O |
| Use cases | `usecases/draw.py`: arrange a code graph as repos > domains > files | `core` |
| Adapters | `adapters/graphify.py` (graph.json in), `adapters/atlas.py` (Atlas spec out) | `usecases`, `core`; never each other |
| Driver | `__main__.py`: command line, files, wiring | everything |

```bash
cd bridge && pip install -r requirements-dev.txt
ruff check . && ruff format --check . && lint-imports
coverage run -m unittest discover -s tests -t . && coverage report      # fails under 75%
ATLAS_INTEGRATION=1 python -m unittest discover -s tests/integration -t .  # real Graphify, pinned version
```

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
```

See `CLAUDE.md` for the rules the code follows.
