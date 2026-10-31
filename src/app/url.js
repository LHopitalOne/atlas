/**
 * Browser glue for the URL hash: writes the current view with history.replaceState and restores it on load or hashchange.
 * The encoding itself is pure and lives in url-codec.js.
 */
import { formatHash, parseHash } from './url-codec.js';
import { route, store } from '../state.js';
import { fitNodes, flyTo } from './camera.js';
import { loadDataset } from './dataset.js';
import { computeRoute, DETAIL, RANK } from './route.js';
import { deselect, select } from './selection.js';
import { setMode, toggleIssues } from '../ui/controls.js';
import { renderRoute } from '../ui/directions.js';

let applying = false;
let selfHash = '';
/** Mirror the current view into the address bar (without adding history entries). */
export function writeHash() {
  if (!store.G || applying) return;
  const n = formatHash({
    dataset: store.G.src,
    selectedId: store.selectedId,
    route,
    issuesOnly: store.issuesOnly,
    colorMode: store.colorMode,
    userColor: store.userColor,
  });
  if (location.hash !== '#' + n) {
    selfHash = '#' + n;
    try {
      history.replaceState(null, '', '#' + n);
    } catch (_) {
      location.hash = n;
    }
  }
}
/** Read the current address-bar hash. */
export function readHash() {
  return parseHash(location.hash);
}
export function applyHashState(o) {
  const g = store.G;
  applying = true;
  if (o.color) {
    store.userColor = true;
    setMode(o.color);
  }
  if (o.issues) toggleIssues(true);
  const okEnd = e =>
    e === null || (e !== undefined && (e.t === 's' ? e.id < g.S : e.t === 'd' ? e.id < g.D : e.id < g.R));
  if (o.hasRoute && okEnd(o.from) && okEnd(o.to) && (o.from || o.to)) {
    route.avoid = !!o.avoid;
    route.links = o.any ? 'any' : 'calls';
    route.from = o.from;
    route.to = o.to;
    route.detailSet = !!o.detail;
    route.detail = o.detail || DETAIL[Math.min(route.from ? RANK[route.from.t] : 2, route.to ? RANK[route.to.t] : 2)];
    route.picking = !route.from ? 'from' : !route.to ? 'to' : null;
    computeRoute();
    renderRoute();
    if (route.path.length > 1) flyTo(fitNodes(route.path, 2), 900);
  } else if (o.node >= 0 && o.node < g.N) select(o.node);
  applying = false;
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  window.addEventListener('hashchange', () => {
    if (applying || location.hash === selfHash) return;
    const o = readHash();
    if (store.G && o.n !== store.G.src) loadDataset(o.n, o);
    else if (store.G) {
      deselect();
      route.from = route.to = null;
      route.picking = null;
      computeRoute();
      renderRoute();
      applyHashState(o);
    }
  });
}
