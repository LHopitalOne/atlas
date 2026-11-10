# Atlas: notes for Claude Code

Atlas draws a service graph (repositories > domains > services > endpoints, plus contracts between endpoints) as a
zoomable map, in the style of Google Maps. It renders with WebGL2 and a 2D canvas overlay, and ships as one HTML file.

Read `docs/DECISIONS.md` first: it lists the deliberate design choices a rebuild must keep.
Read `docs/ARCHITECTURE.md` before changing behaviour, `docs/GRAPH_SPEC.md` before touching data,
and `docs/INTEGRATION.md` when bringing Atlas into another project.

## Commands

```bash
npm install
npm run build        # dist/atlas.html (d3 from CDN) and dist/atlas-offline.html (fully self-contained)
npm test             # unit tests, node:test, ~1 s
npm run test:e2e     # Playwright against dist/atlas-offline.html (run `npm run build` first)
npm run lint         # ESLint: no-undef, complexity <= 25, max 80 lines per function
npm run lint:imports # the layer rules below (test/architecture.test.js)
npm run test:coverage # unit tests; fails under 75% line, branch or function coverage
npm run check        # all of the above, in order
npm run index:self   # regenerate generated/self-graph.json (needs Python + the scip CLI, see tools/index-self/run.sh)
```

E2E uses your Playwright browsers; set `CHROMIUM_PATH` to use another Chromium. WebGL runs on SwiftShader in headless.

## Rules this codebase follows (keep them)

1. **Layers and allowed imports.** `util/` and `config.js` import nothing. `model/` and `graph/` import only `util/math`,
   `util/format` and each other: they are pure and run in Node. `render/` may read `app/` view state (camera, focus,
   route ends) but never imports `ui/`. `ui/` and `app/` may import anything below them. `main.js` wires everything.
2. **No work at import time.** Modules only declare things. DOM wiring goes in an exported `init()` that `main.js`
   calls in a fixed order. GPU resources are created by `initGL()`.
3. **State.** State shared across modules lives in `store` (`src/state.js`), with `cam`, `route`, `stOn` and
   `expanded`. State used by one module stays private to it. Do not add shared `let`s to modules.
4. **The renderer does not call the UI.** UI that must update every frame subscribes with `onFrameDrawn(fn)` or
   `onFrameEnd(fn)` from `render/frame.js`.
5. **HTML.** Panels build HTML strings; every dynamic value goes through `esc()` from `util/format.js`.
6. **Tuning numbers** (sizes, timings, label caps) go in `src/config.js` with a comment, not inline.
7. **Determinism.** Synthetic graphs come from a seeded stream (`model/synthetic.js`); stages must keep their order or
   every share link changes. Layout is deterministic; `test/model.test.js` checks it.
8. **URL hash** uses only letters, digits and hyphens (`app/url-codec.js`), because artifact links pass only `#name`.
9. **Output is one file.** The page must work as a single HTML file: no external assets except the pinned d3-hierarchy
   script (inlined in the offline build). Keep `src/index.html` self-contained.

## Where things are

| Need to change | Go to |
| --- | --- |
| How a graph is generated or laid out | `src/model/synthetic.js`, `src/model/layout.js` |
| Input format for real graphs | `src/model/spec.js` (`validateSpec`, `buildSpec`), `docs/GRAPH_SPEC.md` |
| Route finding | `src/graph/route-search.js` (pure), `src/app/route.js` (state) |
| What draws on the GPU | `src/render/gl.js` (shaders, layers), `src/render/scene.js` (geometry), `src/render/frame.js` (per frame, level of detail) |
| Labels | `src/render/labels.js` (placement tiers, fades), `src/config.js` `LABELS` |
| Roles and impact | `src/graph/insights.js` (pure) |
| Asking about the code | `src/ask/` (tools, offline answers, demo scripts, Claude engine, formatting), `src/ui/ask.js` (panel and playback); `ASK_ENGINE` in `src/config.js` picks simulated or Claude answers |
| What a component does | `src/ui/about.js` (summary, provenance, roles, impact, Copy for AI), `src/ui/code-view.js` (source view) |
| HTTP links between repositories (proofs, impact, arcs, links panel) | `src/model/http.js` (pure), `src/app/http.js`, `src/render/http.js`, `src/ui/proof.js`, `src/ui/links.js`; spec in `docs/GRAPH_SPEC.md` |
| The demo page (real Sentry and Open edX maps) | `tools/demo/build.sh`, `docs/DEMO.md` |
| Panels | `src/ui/*.js` |
| Styles and markup | `src/index.html` (shadcn-style tokens on `:root`) |
| Public JS API | `loadGraph(spec)` in `src/main.js`, exposed as `window.Atlas` |

## The Python bridge (bridge/)

Turns Graphify graph.json files into a graph spec. Clean-architecture rings, enforced by `lint-imports`
(contracts in `bridge/pyproject.toml`): `core` (entities, no I/O) < `usecases` < `adapters` (graphify in, atlas out,
independent of each other) < `__main__` (CLI, files, wiring). `test/fixtures/graphify-shop.json` is the bridge's
golden output; regenerate it with the command in `bridge/tests/test_cli.py` when the mapping changes on purpose.

## After a change

Run `npm run check`. If you changed anything under `src/`, also run `npm run index:self` so the "Self" map matches the
code. If you change visible behaviour, add or adjust a test in `test/e2e/`.
