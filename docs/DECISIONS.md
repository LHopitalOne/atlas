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
- **On mobile the inspector is a bottom sheet with a drag handle.**

## Accessibility

- **The map is a focusable canvas.** Tab reaches it, arrows pan, a reticle marks the centre and Enter opens what is under it.
- **Changes are announced to screen readers,** and opening an item from the keyboard moves focus to its title.

## Sharing

- **The whole view lives in the URL hash,** using only letters, digits and hyphens. It is written with
  `replaceState`, so the Back button is not flooded. Why: artifact links pass only a plain `#name`.
