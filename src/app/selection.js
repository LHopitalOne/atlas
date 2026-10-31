/**
 * Picking (screen point to node, via the spatial grid) and selection: select, deselect, screen-reader descriptions.
 */
import { cam, expanded, route, store } from '../state.js';
import { camFor, fitNodes, flyTo, inspOpen } from './camera.js';
import { updateFocus } from './focus.js';
import { setRouteEnd } from './route.js';
import { writeHash } from './url.js';
import { SVC_MAX_PX } from '../config.js';
import { app, INSP } from '../dom.js';
import { KIND } from '../model/vocab.js';
import { lod, scrR } from '../render/frame.js';
import { announce } from '../ui/feedback.js';
import { openInspector } from '../ui/inspector.js';
import { pushRecent } from '../ui/search.js';
import { $ } from '../util/dom.js';
import { closeSource } from '../ui/code-view.js';

let opener = null;
export function pick(px, py, tolPx = 7) {
  if (!store.G) return null;
  const g = store.G,
    k = cam.k,
    V = lod(k),
    wx = (px - cam.x) / k,
    wy = (py - cam.y) / k,
    gr = g.grid;
  if (V.svcA > 0.3 || V.leafA > 0.3) {
    const reach = (Math.min(g.maxRS * k, SVC_MAX_PX) + 1.4 + tolPx) / k,
      rad = Math.ceil(reach / gr.CELL) + 1,
      gx = Math.floor((wx - gr.x0) / gr.CELL),
      gy = Math.floor((wy - gr.y0) / gr.CELL);
    let best = -1,
      bd = 1e9;
    for (let y = Math.max(0, gy - rad); y <= Math.min(gr.GR - 1, gy + rad); y++)
      for (let x = Math.max(0, gx - rad); x <= Math.min(gr.GC - 1, gx + rad); x++) {
        const cell = y * gr.GC + x;
        for (let j = gr.GO[cell]; j < gr.GO[cell + 1]; j++) {
          const i = gr.GI[j];
          if (i < g.S ? V.svcA < 0.3 : V.leafA < 0.3) continue;
          const d = Math.hypot(g.PX[i] - wx, g.PY[i] - wy) * k - scrR(i);
          if (d < tolPx && d < bd) {
            bd = d;
            best = i;
          }
        }
      }
    if (best >= 0) return { t: 'n', id: best };
  }
  for (let r = 0; r < g.R; r++)
    if (Math.hypot(wx - g.rx[r], wy - g.ry[r]) < g.rR[r]) {
      if (V.dAct > 0.5) {
        for (let d = g.rDs[r]; d < g.rDe[r]; d++)
          if (Math.hypot(wx - g.dcx[d], wy - g.dcy[d]) < g.dR[d]) return V.sAct > 0.6 ? null : { t: 'd', id: d };
        return null;
      }
      return { t: 'r', id: r };
    }
  return null;
}
export const describe = h => {
  const g = store.G;
  if (!h) return '';
  if (h.t === 'r') return `Repository ${g.repoName[h.id]}`;
  if (h.t === 'd') return `Domain ${g.domName[h.id]} in ${g.repoName[g.domRepo[h.id]]}`;
  const s = g.own(h.id);
  return h.id < g.S
    ? `Service ${g.svcName[h.id]} in ${g.repoName[g.domRepo[g.svcDom[h.id]]]}, ${g.domName[g.svcDom[h.id]]}`
    : `${KIND[g.KND[h.id]]} ${g.name(h.id)} on ${g.svcName[s]}`;
};
export function select(id, via) {
  const g = store.G;
  if (id < 0) return deselect();
  if (route.picking) {
    setRouteEnd(route.picking, { t: 's', id: g.own(id) });
    return;
  }
  if (!inspOpen() && document.activeElement && !INSP.contains(document.activeElement)) opener = document.activeElement;
  if (id !== store.selectedId) {
    store.impactId = -1;
    closeSource(false);
  }
  store.selectedId = id;
  expanded.clear();
  pushRecent(id);
  store.placeDirty = true;
  clearTimeout(store.hoverTO);
  store.hover = null;
  updateFocus();
  openInspector(id);
  const svcK = 18 / store.G.medRF,
    t = fitNodes(store.focusList, id < g.S ? 2.4 : 3.2);
  flyTo(t.k >= svcK * 0.6 ? t : camFor(g.PX[id], g.PY[id], Math.max(cam.k, svcK * 1.6)));
  const iss = g.ISS[id] || (id < g.S ? g.SVST[id * 4 + 1] + g.SVST[id * 4 + 2] > 0 : 0);
  announce(`Selected ${describe({ t: 'n', id })}.${iss ? ' Has contract issues.' : ''}`);
  if (via === 'search' || via === 'list')
    requestAnimationFrame(() => {
      const title = $('#insTitle');
      if (title) title.focus({ preventScroll: true });
    });
  writeHash();
}
export function deselect(restore) {
  if (store.selectedId < 0) return;
  store.selectedId = -1;
  store.impactId = -1;
  closeSource(false);
  store.placeDirty = true;
  app.classList.remove('has-insp');
  updateFocus();
  writeHash();
  if (restore && opener && document.contains(opener)) opener.focus({ preventScroll: true });
  opener = null;
}
