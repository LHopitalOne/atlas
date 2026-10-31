/**
 * Route state: ends at any granularity (repository, domain, service), search via graph/route-search,
 * grouping into steps at the chosen level of detail, and the route's geometry on the map.
 */
import { route, store } from '../state.js';
import { fitNodes, flyTo } from './camera.js';
import { refreshRouteFocus } from './focus.js';
import { deselect } from './selection.js';
import { writeHash } from './url.js';
import { RT } from '../dom.js';
import { routeSearch } from '../graph/route-search.js';
import { requestRender } from '../render/frame.js';
import { LY, upload } from '../render/gl.js';
import { put4, theme } from '../render/theme.js';
import { focusRouteField, renderRoute } from '../ui/directions.js';
import { announce } from '../ui/feedback.js';

export const endName = e =>
  !e ? '' : e.t === 's' ? store.G.svcName[e.id] : e.t === 'd' ? store.G.domName[e.id] : store.G.repoName[e.id];
export const endPoint = e =>
  e.t === 's'
    ? [store.G.PX[e.id], store.G.PY[e.id]]
    : e.t === 'd'
      ? [store.G.dcx[e.id], store.G.dcy[e.id]]
      : [store.G.rx[e.id], store.G.ry[e.id]];
const sameEnd = (a, b) => !!a && !!b && a.t === b.t && a.id === b.id;
export const RANK = { r: 0, d: 1, s: 2 };
export const DETAIL = ['repo', 'domain', 'service'];
function endSvcs(e) {
  const g = store.G;
  if (e.t === 's') return [e.id];
  const out = [];
  const d0 = e.t === 'd' ? e.id : g.rDs[e.id],
    d1 = e.t === 'd' ? e.id + 1 : g.rDe[e.id];
  for (let d = d0; d < d1; d++) for (let s = g.dSs[d]; s < g.dSe[d]; s++) out.push(s);
  return out;
}
export function setRouteEnd(which, end) {
  const fromPanel = RT.contains(document.activeElement);
  if (which === 'from') route.from = end;
  else route.to = end;
  route.picking = !route.from ? 'from' : !route.to ? 'to' : null;
  if (!route.detailSet) {
    const r = Math.min(route.from ? RANK[route.from.t] : 2, route.to ? RANK[route.to.t] : 2);
    route.detail = DETAIL[r];
  }
  computeRoute();
  renderRoute();
  if (route.path.length > 1) {
    deselect();
    flyTo(fitNodes(route.path, 2));
    announce(
      `Route found: ${route.hops.length} ${route.hops.length === 1 ? 'hop' : 'hops'}.${route.note ? ' ' + route.note : ''}`,
    );
  } else if (route.picking && fromPanel) focusRouteField();
  else if (route.picking)
    announce(`Choose a ${route.picking === 'to' ? 'destination' : 'start'} on the map or by typing its name.`);
  requestRender();
  writeHash();
}
export function computeRoute() {
  computeRouteCore();
  refreshRouteFocus();
}
function computeRouteCore() {
  const g = store.G;
  route.path = [];
  route.hops = [];
  route.msg = '';
  route.note = '';
  route.hl = -1;
  LY.route.n = 0;
  LY.routeCase.n = 0;
  if (!route.from || !route.to) return;
  if (sameEnd(route.from, route.to)) {
    route.msg = 'The start and destination are the same. Choose a different destination.';
    return;
  }
  const src = endSvcs(route.from),
    tgt = endSvcs(route.to);
  let r = routeSearch(g, src, tgt, { either: route.links === 'any', avoid: route.avoid });
  if (!r && route.links === 'calls') {
    r = routeSearch(g, src, tgt, { either: true, avoid: route.avoid });
    if (r)
      route.note = `No chain of calls leads from ${endName(route.from)} to ${endName(route.to)}, so this route also goes against calls (the dashed steps).`;
  }
  if (!r) {
    route.msg = `${endName(route.from)} and ${endName(route.to)} aren’t connected${route.avoid ? ' without crossing an unmatched contract. Allow unmatched contracts to try again' : ''}.`;
    return;
  }
  if (r.path.length < 2) {
    route.msg = 'One end contains the other. Choose a start and destination that don’t overlap.';
    return;
  }
  route.path = r.path;
  for (let i = 1; i < r.path.length; i++) {
    const v = r.path[i],
      p = r.via[v],
      c4 = [0, 1, 2, 3].map(s => g.dr.c[p * 4 + s]);
    const order = route.avoid ? [0, 3, 1] : [0, 3, 1, 2];
    const st = order.find(s => c4[s] > 0);
    route.hops.push({ a: r.path[i - 1], b: v, st, e: g.dr.rep[p * 4 + st], fwd: !!r.fwd[v] });
  }
  const n = route.hops.length,
    seg = new Float32Array(n * 4),
    prmC = new Float32Array(n * 4),
    prm = new Float32Array(n * 4),
    colC = new Uint8Array(n * 4),
    col = new Uint8Array(n * 4);
  route.hops.forEach((h, j) => {
    seg.set([g.PX[h.a], g.PY[h.a], g.PX[h.b], g.PY[h.b]], j * 4);
    prmC.set([4, 0.1, 0, 4], j * 4);
    prm.set([1.6, 0.1, h.fwd ? 0 : 1, 4], j * 4);
    put4(colC, j, theme.halo, 0.85);
    put4(col, j, theme.route, 1);
  });
  LY.routeCase.n = n;
  upload(LY.routeCase, 0, seg, true);
  upload(LY.routeCase, 1, prmC, true);
  upload(LY.routeCase, 2, colC, true);
  LY.route.n = n;
  upload(LY.route, 0, seg, true);
  upload(LY.route, 1, prm, true);
  upload(LY.route, 2, col, true);
}
// the route's service path, grouped at the chosen level of detail
export function routeSteps() {
  const g = store.G,
    keyOf = s =>
      route.detail === 'repo' ? 'r' + g.domRepo[g.svcDom[s]] : route.detail === 'domain' ? 'd' + g.svcDom[s] : 's' + s;
  const steps = [];
  route.path.forEach((s, i) => {
    const k = keyOf(s),
      last = steps[steps.length - 1];
    if (last && last.key === k) {
      last.n++;
      return;
    }
    steps.push({ key: k, s, n: 1, hop: i > 0 ? i - 1 : -1 });
  });
  return steps;
}
export const stepName = st => {
  const t = st.key[0],
    id = +st.key.slice(1);
  return t === 'r' ? store.G.repoName[id] : t === 'd' ? store.G.domName[id] : store.G.svcName[id];
};
