/**
 * Focus and dimming: hover highlights a node's neighbourhood without dimming; a selection or a route
 * dims everything else and lights up what is connected. Animated via store.focusT / store.dimT.
 */
import { route, store } from '../state.js';
import { requestRender } from '../render/frame.js';
import { LY, patch, upload } from '../render/gl.js';
import { put4, theme } from '../render/theme.js';
import { impactOf, pairContract } from '../graph/insights.js';
import { fitNodes, flyTo } from './camera.js';
import { announce } from '../ui/feedback.js';

export function computeFocus(id) {
  const g = store.G;
  for (const i of store.focusList) store.inF[i] = 0;
  store.focusList = [];
  store.focusEdges = [];
  const add = i => {
    if (!store.inF[i]) {
      store.inF[i] = 1;
      store.focusList.push(i);
    }
  };
  add(id);
  add(g.own(id));
  const roots = [id];
  if (id < g.S)
    for (let i = g.sLs[id]; i < g.sLe[id]; i++) {
      roots.push(i);
      add(i);
    }
  for (const r of roots)
    for (let j = g.AO[r]; j < g.AO[r + 1]; j++) {
      const e = g.AE[j];
      if (r !== id && (g.CS[e] === id || g.CD[e] === id)) continue;
      store.focusEdges.push(e);
      const a = g.CS[e],
        b = g.CD[e];
      add(a);
      add(b);
      add(g.own(a));
      add(g.own(b));
    }
  if (store.impactId === id && id < g.S) {
    // impact view: everything that could break, with the call chains that lead to it
    const im = impactOf(g, id);
    for (const t of im.services) {
      add(t);
      const e = pairContract(g, im.via[t]);
      if (e >= 0) store.focusEdges.push(e);
    }
  }
  for (let j = 0; j < store.A.svcs.n; j++) store.A.svcs.fl[j * 2] = 0;
  for (let j = 0; j < store.A.leaves.n; j++) store.A.leaves.fl[j * 2] = 0;
  for (const i of store.focusList) {
    if (i < g.S) store.A.svcs.fl[i * 2] = 255;
    else store.A.leaves.fl[(i - g.S) * 2] = 255;
  }
  patch(LY.svcs, 2, store.A.svcs.fl);
  patch(LY.leaves, 2, store.A.leaves.fl);
  const fe = store.focusEdges.slice(0, 20000),
    spokes = id < g.S ? g.sLe[id] - g.sLs[id] : 0,
    n = fe.length + spokes;
  const seg = new Float32Array(n * 4),
    prm = new Float32Array(n * 4),
    col = new Uint8Array(n * 4);
  const strong = [
    [theme.text, 0.55],
    [theme.st[1], 1],
    [theme.st[2], 1],
    [theme.st[3], 0.95],
  ];
  fe.forEach((e, j) => {
    const a = g.CS[e],
      b = g.CD[e],
      st = g.CST[e];
    seg.set([g.PX[a], g.PY[a], g.PX[b], g.PY[b]], j * 4);
    prm.set([1.7, 0.13, st === 3 ? 1 : 0, st], j * 4);
    put4(col, j, strong[st][0], strong[st][1]);
  });
  for (let k = 0; k < spokes; k++) {
    const j = fe.length + k,
      i = g.sLs[id] + k;
    seg.set([g.PX[id], g.PY[id], g.PX[i], g.PY[i]], j * 4);
    prm.set([0.9, 0, 0, 4], j * 4);
    put4(col, j, theme.edge, theme.edge[3]);
  }
  LY.focusE.n = n;
  upload(LY.focusE, 0, seg, true);
  upload(LY.focusE, 1, prm, true);
  upload(LY.focusE, 2, col, true);
}
export function clearFocus() {
  for (const i of store.focusList) store.inF[i] = 0;
  store.focusList = [];
  store.focusEdges = [];
  LY.focusE.n = 0;
  for (let j = 0; j < store.A.svcs.n; j++) store.A.svcs.fl[j * 2] = 0;
  for (let j = 0; j < store.A.leaves.n; j++) store.A.leaves.fl[j * 2] = 0;
  patch(LY.svcs, 2, store.A.svcs.fl);
  patch(LY.leaves, 2, store.A.leaves.fl);
}
// what gets the spotlight: a selection, else a route (hover then only rings and labels), else whatever is hovered
/** Two hover targets ({t, id} or null) are the same thing. */
export const same = (a, b) => (!a && !b) || (a && b && a.t === b.t && a.id === b.id);
export const ROUTE_FOCUS = 2 ** 30;
/** Focus id for the items an Ask answer is showing on the map. */
export const ASK_FOCUS = 2 ** 30 + 1;
export const routeActive = () => route.path.length > 1;
export function updateFocus() {
  const hid = store.hover && store.hover.t === 'n' ? store.hover.id : -1,
    id = store.selectedId >= 0 ? store.selectedId : routeActive() ? -1 : hid;
  if (id >= 0) {
    if (id !== store.focusId) {
      computeFocus(id);
      store.focusId = id;
    }
    store.focusGoal = 1;
  } else if (routeActive()) {
    if (store.focusId !== ROUTE_FOCUS) {
      computeRouteFocus();
      store.focusId = ROUTE_FOCUS;
    }
    store.focusGoal = 1;
  } else if (store.askSet.length) {
    if (store.focusId !== ASK_FOCUS) {
      computeSetFocus(store.askSet);
      store.focusId = ASK_FOCUS;
    }
    store.focusGoal = 1;
  } else store.focusGoal = 0;
  store.dimGoal =
    store.selectedId >= 0 ||
    (store.focusId === ROUTE_FOCUS && routeActive()) ||
    (store.focusId === ASK_FOCUS && store.askSet.length)
      ? 1
      : 0;
  requestRender();
}
// route spotlight: the services on the path plus the endpoints each hop's contract runs between
export function computeRouteFocus() {
  const g = store.G;
  for (const i of store.focusList) store.inF[i] = 0;
  store.focusList = [];
  store.focusEdges = [];
  const add = i => {
    if (i >= 0 && !store.inF[i]) {
      store.inF[i] = 1;
      store.focusList.push(i);
    }
  };
  for (const s of route.path) add(s);
  for (const h of route.hops)
    if (h.e >= 0) {
      add(g.CS[h.e]);
      add(g.CD[h.e]);
    }
  for (let j = 0; j < store.A.svcs.n; j++) store.A.svcs.fl[j * 2] = 0;
  for (let j = 0; j < store.A.leaves.n; j++) store.A.leaves.fl[j * 2] = 0;
  for (const i of store.focusList) {
    if (i < g.S) store.A.svcs.fl[i * 2] = 255;
    else store.A.leaves.fl[(i - g.S) * 2] = 255;
  }
  patch(LY.svcs, 2, store.A.svcs.fl);
  patch(LY.leaves, 2, store.A.leaves.fl);
  LY.focusE.n = 0;
}
export function refreshRouteFocus() {
  if (routeActive() && store.focusId === ROUTE_FOCUS) store.focusId = -1;
  updateFocus();
}
// hover intent: highlight only after the pointer settles, so sweeping across the map never flickers
export function setHover(h, immediate) {
  if (same(h, store.hover)) return;
  store.hover = h;
  requestRender();
  clearTimeout(store.hoverTO);
  store.hoverTO = setTimeout(updateFocus, immediate || store.selectedId >= 0 ? 0 : 110);
}

/** Show or hide, on the map, everything a change to service id could affect. */
export function toggleImpact(id) {
  store.impactId = store.impactId === id ? -1 : id;
  store.focusId = -1;
  updateFocus();
  const btn = document.querySelector('[data-impact]');
  if (btn) {
    const on = store.impactId === id;
    btn.setAttribute('aria-pressed', String(on));
    btn.textContent = on ? 'Hide on map' : 'Show on map';
  }
  if (store.impactId === id)
    flyTo(
      fitNodes(
        store.focusList.filter(i => i < store.G.S),
        1.6,
      ),
    );
  announce(
    store.impactId === id ? `Showing everything a change to ${store.G.name(id)} could affect.` : 'Impact view off.',
  );
}

/** Light up a set of map items (an answer's citations): nodes with their services, territories with their services. */
export function computeSetFocus(refs) {
  const g = store.G;
  for (const i of store.focusList) store.inF[i] = 0;
  store.focusList = [];
  store.focusEdges = [];
  const add = i => {
    if (i >= 0 && !store.inF[i]) {
      store.inF[i] = 1;
      store.focusList.push(i);
    }
  };
  for (const ref of refs) {
    const t = ref[0],
      id = +ref.slice(1);
    if (t === 'n') {
      add(id);
      add(g.own(id));
    } else {
      const [d0, d1] = t === 'd' ? [id, id + 1] : [g.rDs[id], g.rDe[id]];
      for (let d = d0; d < d1; d++) for (let s = g.dSs[d]; s < g.dSe[d] && store.focusList.length < 2000; s++) add(s);
    }
  }
  for (let j = 0; j < store.A.svcs.n; j++) store.A.svcs.fl[j * 2] = 0;
  for (let j = 0; j < store.A.leaves.n; j++) store.A.leaves.fl[j * 2] = 0;
  for (const i of store.focusList) {
    if (i < g.S) store.A.svcs.fl[i * 2] = 255;
    else store.A.leaves.fl[(i - g.S) * 2] = 255;
  }
  patch(LY.svcs, 2, store.A.svcs.fl);
  patch(LY.leaves, 2, store.A.leaves.fl);
  LY.focusE.n = 0;
}
