# Design decisions

The prototype is the design reference for a rebuild. The code shows *what* it does; this page marks which details are
deliberate, so a rewrite keeps them. Each entry says why. Values live in `src/config.js` and the tokens in `src/index.html`.

## Map model

- **It reads like a geographic map.** Repositories are countries, domains are states, services are cities, endpoints are
  streets. Each level appears only once it is legible at the current zoom. Why: people already know how to read maps,
  so a 100k-node graph needs no explanation.
- **Busy neighbours sit together.** Siblings are ordered by how much they talk to each other before circle packing, and
  endpoints sit on the side of their service that faces their partners. Why: shorter, less tangled lines.
- **Synthetic graphs are deterministic per size.** Why: shared links and screenshots stay valid.

## Labels (Google Maps model)

- **Text stays the same size at every zoom.** Labels are pinned to map points and do not scale. Why: scaled text is
  unreadable when small and shouts when large.
- **Labels appear by tier and never overlap.** The order is repositories, domains, services, endpoints. A territory's
  name shows only once it fits inside the territory, anchored to its top edge. Service discs count as obstacles, so a
  name never covers a city.
- **Placement is throttled and sticky.** A pass runs at most every 250 ms while moving and once after the camera settles.
  Labels shown in the last pass keep priority. Why: labels must not shuffle or flicker during a pan.
- **Labels fade, never pop.** Each fades on its own clock: 200 ms in, 140 ms out. Exits are faster than entrances.
- **The selection, the hovered item and route ends always keep their labels.**

## Nodes, lines and colour

- **Markers stop growing.** Services cap at 26 px on screen and endpoints at 6.5 px, like map markers. Why: deep zoom
  shows more space, not giant circles.
- **Nodes at rest are a thin ring with a dot; only focused nodes are solid.** Why: the map stays quiet until you ask.
- **Bundles are hairlines whose opacity, not width, shows traffic.** Why: width-coded bundles turn into a wall of ink.
- **At coarse zoom only the backbone is drawn.** That is each territory's three strongest links plus the busiest tenth.
- **Only the five largest repositories get a colour; the rest stay neutral.** Why: at 100k nodes there are 91
  repositories, and 91 hues mean nothing. Repo colouring is the default with five or fewer repositories and for Self;
  Health is the default otherwise.
- **Health is grey until it matters.** A service is neutral below a 15% issue share, turns amber by 30% and red by 55%.
  Why: colour should point at problems, not decorate.
- **Territory fills fade from full at the top edge to about 10% at the bottom.** Why: territories read clearly without
  covering the lines.

## Focus

- **Hover never dims the map.** It adds a ring and a label after a 110 ms intent delay. Why: moving the pointer across
  the map must not make it flash.
- **Selecting dims everything else to about 14%** and lights up the neighbourhood and its contracts.
- **A route dims everything except its path,** with dots flowing from start to destination at a steady on-screen speed.
- **Off-screen neighbours get edge chips.** These are arrows with counts at the screen edge, pointing to hidden
  connections of the selection, and clicking one reveals them.

## Understanding a component

- **The inspector answers "what is this, and should I care?" first.** Order: what it does, where that text came from,
  roles, signature and location, then stats, impact and connections. Why: people decide from the summary; the lists are
  for checking.
- **Every summary says where it came from:** a doc comment, an AI summary (with the commit), or simulated demo text.
  Why: people and AI agents must know how far to trust it, and AI summaries read by other AIs compound mistakes.
- **Roles are computed from the graph, never written by AI.** Entry point (nothing calls it), hub (top 5% by callers,
  at least 5), bridge (called from another repository and calls on into a repository that itself calls onward, so
  using a library does not count), dead end (calls nothing), isolated.
- **Impact means every service that calls it, directly or through others.** "Show on map" lights up those services and
  the call chains that lead to them. Why: it is the question asked before every change, and the map shows it best.
- **Code is shown, never stored.** The panel shows the signature; "View source" opens a wider view of the definition,
  fetched live from GitHub at the indexed commit with the viewer's own access, labelled "not stored". The prototype
  bundles its own source to stand in for GitHub.
- **AI agents get the same answers as people.** "Copy for AI" gives identity, summary with its source, signature, roles,
  impact, connections, location and a map link, as plain Markdown.
- **Search works by meaning as well as by name.** Matches on summaries appear in their own group, "By what it does",
  with the matching words marked. The product would use embeddings of the summaries (not of the code).

## Asking about the code

- **The search bar is the one way in.** Typing a question offers "Ask Atlas: …" first; typing a name offers it last.
  `A` or the "Ask Atlas" action opens it empty. Why: one box for finding, asking and acting; no competing chat bubble.
- **The conversation lives in the left panel,** one left panel at a time: opening Ask closes Directions and Needs
  attention (and the other way round), and the Key folds while it is open.
- **Every map item an answer mentions is a numbered chip,** listed again under Sources. Hovering a chip or source rings
  the item on the map; clicking selects it (territories fly into view). "Show on map" dims everything except the
  answer's items. Why: answers should be checkable at a glance, and the map is the best place to check them.
- **The answer shows what it looked at** ("Searched the index", "Checked the impact of …", "Read the code of … (live,
  not stored)"), collapsed to one line when done. Why: people and agents see whether code was read or only the index.
- **Answers trace their path on the map.** The items an answer cites are joined in reading order by the shortest call
  chain between each pair (at most three hops), drawn like a route: lines in the route colour, dashed against the call,
  dots flowing along them. The trail grows while the answer streams. When it finishes, the camera moves only if the
  items are off screen or too small to read.
- **Answers that describe an order get a diagram** (`ASK_DIAGRAM = 'diagram'`): stage boxes with their items, joined
  by arrows that draw themselves, or for routes a chain of items with arrows labelled "calls" / "called by". Drawn as
  SVG in the design system, every item a button. The alternative (`'steps'`) is a step line: one stop per step (a
  route's services, or a pipeline's stages with their functions). Solid along calls, dashed against them; each stop is
  clickable and rings on the map; stops appear 45 ms apart when the answer finishes. Why not a rendered Mermaid diagram:
  the map already shows where things are, a diagram can't link to the map, and the library is heavier than all of Atlas.
  The step line adds the one thing the map can't show at a glance: order. It comes from a `FLOW:` line in the answer,
  which Claude is asked for too.
- **"Copy as Mermaid"** exports an answer as a Mermaid flowchart (stages as subgraphs, calls as labelled edges), to
  paste into docs, pull requests or an AI agent. Mermaid is for sharing, not for reading inside Atlas.
- **Sources fold into one line** ("17 sources · build, buildSpec, finish +14") that opens to the list; the numbered
  chips in the text are the main way in.
- **Cycle questions are answered from the graph, not guessed.** "Are there any dependency cycles?", "circular imports
  between modules?", "Is X part of a cycle?" use real cycle detection (strongly connected components) on calls between
  services and between domains/modules, and show the shortest loop: in the text, as a diagram chain that comes back to
  its start, and as a trail on the map. Answers say why it matters (nothing in a cycle can change or be tested alone).
- **Selection is context:** an "About …" chip shows what "this" means; `@` mentions items by name.
- **Claude answers when the page may ask it** (the viewer's own account, with consent); otherwise an offline answerer
  handles the common questions from the index, and the panel says "Offline · answered from the index, without AI".
  Both use the same tools (search, describe, impact, route, overview, read_source), which are also what agents get.
- **Answers play out, they don't pop in.** "Thinking…", then each step appears with a spinner that turns into a check
  (and rings the item it looked at on the map), then the text streams in word by word with chips popping in and sources
  sliding in as they are cited. When it finishes, the answer's items light up on the map. Stop ends it where it is.
  Entrance animations carry the time they started, so re-rendering a streaming answer never restarts them. With
  reduced motion everything appears at once.
- **The prototype simulates answers** (`ASK_ENGINE = 'demo'` in `src/config.js`): a scripted walkthrough for questions
  about rendering, cited against Atlas's real functions, and offline answers for the rest, labelled "Demo" and
  "Simulated answer". The Claude engine is kept behind the same switch for the product.
- **Composer:** grows with the text, Enter sends, Shift+Enter adds a line, Send becomes Stop while answering, Escape
  closes the panel and returns focus to the map.

## Directions

- **Either end can be a repository, domain, service or endpoint.** Typing or clicking works in both fields. After the
  start is chosen, focus moves straight to the destination field.
- **"Calls only" is the default.** If no chain of calls exists, the route falls back to either direction and says so.
- **Steps against the call direction are dashed and marked ↑.** A legend explaining solid, dashed and moving dots appears
  with every route.
- **Weak links are named.** When two services are joined only because both use a shared service (one used by 5% or more
  of all services), the panel says that this does not mean one depends on the other.

## Motion (Emil Kowalski's rules)

- **Three curves:** ease-out `(.23,1,.32,1)` for UI, ease-in-out `(.77,0,.175,1)` for camera moves,
  drawer `(.32,.72,0,1)` for panels.
- **Keyboard actions are instant;** only pointer and UI actions animate. Why: keyboard users repeat actions quickly.
- **Panels enter in 260 ms and exit in 180 ms.** Buttons press to `scale(.97)`.
- **Hover effects apply only on devices that can hover.** The dock tooltip waits 350 ms the first time, then is instant.
- **Long camera flights pull back mid-flight,** so you see where you are going.
- **Reduced motion is respected everywhere.**

## Interface

- **Visual language:** shadcn and Vercel style. Neutral OKLCH tokens, the Geist font, a black canvas, thin rounded
  scrollbars.
- **Search is a command palette.** Results are grouped repositories, domains, services, endpoints. When empty, it shows
  recent items and quick actions with their shortcuts.
- **The Key folds away while a side panel is open** and restores afterwards. Why: the left side stays readable.
- **Panels share one layout system.** The map controls are one card of one width: actions, zoom slider, minimap,
  quiet stats. Segmented controls span their row with equal segments. Inspector actions form one row of round
  buttons that never wraps.
- **On phones the inspector and the left panels (Ask, Directions, Needs attention) are bottom sheets,** and the camera
  treats the sheet as covered space, so what you're looking at stays visible above it.
- **Panels never cover the toolbar or each other.** The source view starts where the inspector starts and sits beside it.
  In narrow windows with the inspector open, the map controls shrink to the dock and the Key steps aside until it fits.
- **The minimap box only draws edges that are really inside the overview,** and nothing when the whole map is in view.
  Why: a box clamped to the minimap's border looks like a frame, not like "you are here".
- **In the source view, line numbers stay pinned and the definition is highlighted across the full line.**

## Accessibility

- **The map is a focusable canvas.** Tab reaches it, arrows pan, a reticle marks the centre and Enter opens what is under it.
- **Changes are announced to screen readers,** and opening an item from the keyboard moves focus to its title.

## Sharing

- **The whole view lives in the URL hash,** using only letters, digits and hyphens. It is written with
  `replaceState`, so the Back button is not flooded. Why: artifact links pass only a plain `#name`.
