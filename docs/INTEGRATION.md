# Integrating Atlas into another project

Pick the path that matches how deep the integration needs to go.

## 1. Use the built page as is, with your graph

Fastest. Atlas stays a standalone page (or an iframe in your app).

- **Build time:** produce a graph spec (docs/GRAPH_SPEC.md), then
  `node scripts/build.mjs --offline --graph=path/to/graph.json`. The "Self" view shows your graph.
- **Run time:** call `window.Atlas.loadGraph(spec)` in the page (or `iframe.contentWindow.Atlas.loadGraph(spec)`).
  It validates the spec and throws an error that lists every problem.

## 2. Reuse the engine inside your app

For a React, Vue or Svelte app that should own the panels.

**Lift as is (pure, no DOM):**
- `src/model/` (generation, spec validation, layout, indexes): `buildSpec(spec)` returns the graph object
  described in docs/ARCHITECTURE.md.
- `src/graph/route-search.js` for routes, `src/app/url-codec.js` for shareable state, `src/render/collision.js`
  for label placement.

**Keep, behind a thin adapter:** `src/render/` and `src/app/` (camera, focus, selection, route). They need two
canvases (`#gl` for WebGL2, `#ov` for the overlay) and read `store`. Give the adapter a mount function that creates
the canvases, calls `initGL()` and the `init()` functions of `app/pointer.js` and `render/minimap.js`, and loads a graph.

**Replace with your components:** `src/ui/` (panels). The seams they use are small:
- read: `store.selectedId`, `store.G`, `route`, `store.colorMode`, `store.issuesOnly`
- act: `select(id)`, `deselect()` (app/selection), `setRouteEnd(which, end)`, `computeRoute()` (app/route),
  `flyTo(fitNodes(ids))` (app/camera), `setMode(mode)`, `toggleIssues()` (ui/controls: move these into app/ when you
  replace the toolbar)
- react to frames: `onFrameDrawn(fn)`, `onFrameEnd(fn)` (render/frame)
- react to state changes: today the app calls `openInspector`, `renderRoute` and `renderAttn` directly. When you
  replace those panels, put a small event emitter on `store` (for example `emit('select', id)`) and subscribe your
  components instead.

**Before mounting more than one map per page:** move `store`, `cam`, `route` and the `dom.js` references into a
per-instance context passed to `init()`. The modules already take everything else as arguments or imports, so this
is mechanical.

## 3. Index your own code

`tools/index-self/index_self.py` builds a spec from JavaScript or TypeScript with tree-sitter and SCIP. For another
repository, keep the SCIP resolution and the "Resolved / Ambiguous / Unresolved / Inferred" model, change `layer()`
to map your folders or packages to repos, and drop the page-specific CSS, markup and shader passes.

## Checklist after integrating

- `npm run check` passes (lint, unit, build, end-to-end).
- Your graph passes `validateSpec`.
- Links still work: the URL hash keeps to letters, digits and hyphens.
- Reduced motion, keyboard navigation (Tab to the map, arrows, Enter) and screen-reader announcements still work.
