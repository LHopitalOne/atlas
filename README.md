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
each repository gets its own territory. Tests: `cd bridge && python3 -m unittest discover -s tests -t .`

Licence: Apache-2.0.

## Scripts

| Command | What it does |
| --- | --- |
| `npm run build` | Bundle `src/` with esbuild into the two single-file pages |
| `npm test` | Unit and architecture tests (Node's test runner) |
| `npm run test:e2e` | Browser tests with Playwright (set `CHROMIUM_PATH` to use a specific Chromium) |
| `npm run lint` | ESLint |
| `npm run check` | Lint, unit tests, build, end-to-end tests |
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
```

See `CLAUDE.md` for the rules the code follows.
