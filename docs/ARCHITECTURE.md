# Architecture

## Overview

```
 data                 layout                    GPU + overlay                    panels
 model/synthetic.js ─┐                          render/scene.js  (build once)    ui/*.js
 model/spec.js ──────┼─> model/layout.js ─> G ─> render/frame.js (per frame) ─> render/overlay.js, labels.js
 (Atlas.loadGraph)   ┘   model/graph-index.js        render/gl.js (shaders)        frame hooks ─> ui/where, zoom, perf
                                                     ▲
              app/*.js: camera, focus, selection, route, url, keys, pointer (state changes ─> requestRender)
```

One graph object `G` (in `store.G`) is built per dataset and never mutated afterwards. Everything else is view state.
The page renders only when something changes (`requestRender()`), not continuously.

## Layers

| Layer | Folder | May import | Notes |
| --- | --- | --- | --- |
| Utilities | `util/`, `config.js` | nothing | `util/math` and `util/format` are pure; `util/dom` is browser-only |
| Model | `model/`, `graph/` | util/math, util/format, each other | Pure; runs in Node; unit-tested |
| State | `state.js`, `dom.js` | nothing / util | `store`, `cam`, `route`; fixed DOM references |
| Render | `render/` | model, state, util, app (read view state) | Never imports `ui/`; exposes frame hooks |
| App | `app/` | everything below | Camera, focus, selection, routing, URL, input |
| UI | `ui/` | everything below | Panels; each wires itself in `init()` |
| Entry | `main.js` | everything | Support check, `init()` order, boot, `loadGraph` API |

`test/architecture.test.js` enforces the import rules, "no work at import time" and module headers.

## The graph object (`store.G`)

Built by `finish()` in `model/layout.js` from either generator. Node ids: services `0..S-1`, leaves `S..N-1`.

| Group | Fields |
| --- | --- |
| Sizes | `N S L R D C` (nodes, services, leaves, repos, domains, contracts) |
| Hierarchy | `domRepo`, `rDs/rDe` (repo's domain range), `svcDom`, `dSs/dSe`, `leafSvc`, `sLs/sLe`, `own(i)` (service of a node), `name(i)` |
| Contracts | `CS CD CST` (source, target, status), `AO AE` (CSR adjacency per node), `ISS` (worst issue per node), `SVST` (status counts per service), `REL`, `BYST` |
| Aggregates | `sp dp rp` (undirected pairs between services, domains, repos: `{a,b,c,n,map}`), `dr` (directed service pairs with a representative contract per status), `RO RI` (forward CSR over `dr`) |
| Positions | `PX PY PR` (node centre and radius), `RS RF` (service disc and footprint radius), `dcx dcy dR`, `rx ry rR` |
| Territories | `dHull rHull` (flat convex hulls), `dTop rTop` (label anchors) |
| Lookup | `grid` (uniform CSR grid for picking), `bounds`, `svcOrder domOrder repoOrder` (label priority), `medRF` etc. |
| Descriptions | `doc(i)`, `sig(i)`, `loc(i)`, `end(i)`: summary, signature, location, last line (from the spec, or simulated for demo graphs in `model/describe.js`) |
| Meta | `src` (`'self'` or a size), `meta` (labels, `commit`, `docSource`, `sourceBundle`), `tGen tLay bytes` |

## State

`store` (`src/state.js`) holds state shared across modules: the graph, viewport size, colour mode, hover and selection,
focus and dimming animation (`focusT`, `dimT`), label placement (`placed`, `labelA`, `labelSide`), search index,
perf counters. `cam` is the view transform (`screen = world * k + (x, y)`). `route` is the directions state.
State used by a single module is a private `let` in that module.

## Frame pipeline (`render/frame.js`)

1. `lod(k)` picks what is legible at this zoom: repository bundles, then domain bundles, services, endpoints.
2. Background grid, then territory fills (`P_FILL`), then edge layers (`P_EDGE`: instanced quadratic curves with dashes
   and end fades), then nodes (`P_NODE`: SDF circles, diamonds and squares). Layers live in `LY`, built by `render/scene.js`.
3. The 2D overlay (`render/overlay.js`): hover outline, flow dots, rings, route pins, off-screen chips, reticle, labels.
4. Frame hooks: `onFrameDrawn(fn(V))` subscribers (breadcrumb, zoom slider), then `onFrameEnd(fn(now))` (perf readout).

Focus and dimming are animated per frame from `store.focusT` and `store.dimT`; everything else is static geometry.

## Labels (`render/labels.js`)

Google Maps model: fixed-size text pinned to map points. Pinned labels (selection, hover, route ends) reserve space
first. A placement pass then fills tiers in order (repositories, domains, services, endpoints) with a collision grid
(`render/collision.js`); it runs at most every 250 ms while moving and once after settling. Labels shown last pass keep
priority, so labels don't shuffle. Each label fades on its own clock. Tuning lives in `config.js` (`LABELS`).

## Routing

`graph/route-search.js` is a multi-source breadth-first search over the directed service table. With
`either: true` it also walks calls backwards, which can join two services only because both use a third; the
Directions panel names such weak links. `app/route.js` turns repository and domain ends into service sets, groups
steps at the chosen detail, and builds the route's geometry.

## Understanding a component

`graph/cycles.js` (pure) finds dependency cycles (iterative Tarjan, so 100k nodes don't hit recursion limits) and
the shortest loop through any member. `graph/insights.js` (pure) computes roles (`rolesOf`) and impact (`impactOf`: every transitive caller, nearest first,
with the pair that reached each). `ui/about.js` renders the summary, provenance, roles, signature and impact, and builds
the "Copy for AI" text. `ui/code-view.js` shows a definition's lines from `meta.sourceBundle`. Impact on the map is a
focus mode: `store.impactId` makes `computeFocus` add the affected services and chains.

## Asking about the code

`ask/tools.js` (pure) is the set of lookups every answerer uses: search, describe, impact, route, overview and, when
source is available, read_source. `ask/local.js` (pure) answers common questions from those tools without AI;
`ask/claude.js` gives the same tools to Claude through the artifact `sample` capability and asks it to cite items as
`[[ref]]`; `ask/format.js` (pure) turns answers into safe HTML with numbered citations and follow-ups. `ask/demo.js` (pure) scripts simulated answers for the prototype
(`ASK_ENGINE = 'demo'`): the rendering walkthrough and offline answers, played by `ui/ask.js`, which is the panel. "Show on map" is a focus mode like routes: `store.askSet` makes `computeSetFocus` light up the cited items.

## HTTP links between repositories

`model/http.js` (pure) indexes `spec.links` into `G.http`: links grouped by the arc they draw (caller to endpoint),
by node, plus `httpImpact` (everything in other repositories that calls an endpoint, a file or a repository) and the
arc geometry shared by drawing and picking. `render/http.js` draws every arc on the overlay, coloured by proof, with
an endpoint marker and arrowhead at every zoom, flow dots on the hot ones and a tooltip on hover. `app/http.js` picks
arcs (`pick()` tries nodes first, then arcs, then territories), opens a link's proof (`store.linkId`) and toggles
the impact view (`store.httpImpact`, `'n<id>'` or `'r<id>'`); `computeHttpFocus` in `app/focus.js` lights them up.
`ui/proof.js` builds the proof, endpoint and accuracy HTML; `ui/links.js` is the links panel, the home panel of maps
that have links. Builds with `--maps=key:spec.json:Label,...` embed real maps, each parsed only when shown
(`model/maps.js`); the dataset control then offers those maps instead of Self and the synthetic sizes.

## URL

`#<dataset>[-node-<id>][-route-<from>-<to>[-avoid][-any][-by<detail>]][-issues][-<colour>]`, ends as
`<serviceId>`, `r<repo>`, `d<domain>` or `x`. Pure codec in `app/url-codec.js`; written with `history.replaceState`.

## Self-indexing

`tools/index-self/` indexes `src/` with tree-sitter (structure) and scip-typescript (references) into
`generated/self-graph.json`, which the build embeds. Each module is a domain, grouped by layer.

## Known debt (next candidates)

- **Single instance.** Modules hold page-level state and `dom.js` looks up fixed ids, so one page hosts one Atlas.
  To mount several, turn `store` and `dom` into a per-instance context (see docs/INTEGRATION.md).
- **HTML strings.** Panels build HTML strings with manual `esc()`. A templating layer with automatic escaping
  (lit-html, or your framework) would remove that risk.
- **Complexity.** 12 functions are between complexity 15 and 25 (`npx eslint src --rule '{"complexity":["warn",15]}'`),
  mostly panel builders and pointer handlers. All are under the enforced cap of 25.
- **Types.** JSDoc covers the pure modules and public API; the rest is untyped JavaScript.
- **d3-hierarchy** is a global from a pinned script tag (inlined in the offline build), used only by `model/layout.js`.
