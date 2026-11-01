/**
 * Dataset lifecycle: build or load a graph, reset view state, upload it to the GPU, refresh every panel.
 */
import { cam, expanded, route, store } from '../state.js';
import { fitBox, flyTo, viewCenter } from './camera.js';
import { computeFocus, computeRouteFocus, ROUTE_FOCUS } from './focus.js';
import { computeRoute } from './route.js';
import { applyHashState, writeHash } from './url.js';
import { app, BLD, glc, ov } from '../dom.js';
import { selfSpec } from '../model/self.js';
import { buildSpec } from '../model/spec.js';
import { build } from '../model/synthetic.js';
import { DEFAULT_KIND, DEFAULT_STATUS, KIND, STATUS } from '../model/vocab.js';
import { requestRender } from '../render/frame.js';
import { measure } from '../render/canvas.js';
import { buildScene, recolor } from '../render/scene.js';
import { readTheme } from '../render/theme.js';
import { buildAttn, renderAttn } from '../ui/attention.js';
import { setGroup, syncThumb } from '../ui/controls.js';
import { renderRoute } from '../ui/directions.js';
import { announce, toast } from '../ui/feedback.js';
import { openInspector } from '../ui/inspector.js';
import { renderLegend } from '../ui/legend.js';
import { renderPerf } from '../ui/perf.js';
import { loadRecent } from '../ui/search.js';
import { $ } from '../util/dom.js';
import { fmt } from '../util/format.js';
import { resetAsk } from '../ui/ask.js';

export function loadDataset(n, state) {
  const hadState = store.G && (store.selectedId >= 0 || !!route.from || !!route.to);
  setGroup($('#scale'), n);
  $('#scaleSel').value = String(n);
  $('#buildMsg').textContent = n === 'self' ? 'Loading Atlas’s own code graph…' : `Building ${fmt(n)} nodes…`;
  BLD.classList.add('on');
  setTimeout(() => {
    requestAnimationFrame(() => {
      store.selectedId = -1;
      store.hover = null;
      store.focusId = -1;
      store.focusT = 0;
      store.focusGoal = 0;
      store.dimT = 0;
      store.dimGoal = 0;
      app.classList.remove('has-insp');
      expanded.clear();
      route.from = route.to = null;
      route.picking = null;
      route.detailSet = false;
      route.path = [];
      route.hops = [];
      store.IDX = null;
      measure.clear();
      store.placed = new Map();
      store.labelA = new Map();
      store.labelSide.clear();
      store.placeDirty = true;
      store.G = n === 'self' ? buildSpec(selfSpec()) : build(n);
      store.G.src = n;
      resetAsk();
      store.inF = new Uint8Array(store.G.N);
      // labels come from the dataset: indexed code uses its own vocabulary for statuses and kinds
      STATUS.splice(0, 4, ...((store.G.meta && store.G.meta.status) || DEFAULT_STATUS));
      KIND.splice(0, 4, ...((store.G.meta && store.G.meta.kind) || DEFAULT_KIND));
      store.focusList = [];
      store.focusEdges = [];
      store.repoRank = new Uint16Array(store.G.R);
      store.G.repoOrder.forEach((r, i) => (store.repoRank[r] = i));
      if (!store.userColor) store.colorMode = store.G.R <= 5 || n === 'self' ? 'repo' : 'health';
      setGroup($('#seg'), store.colorMode);
      loadRecent();
      buildAttn();
      const tUp = buildScene();
      store.buildInfo = { t: store.G.tGen + store.G.tLay + tUp, bytes: store.G.bytes + store.gpuBytes };
      $('#count').innerHTML = `<b>${fmt(store.G.N)}</b> nodes&nbsp; <b>${fmt(store.G.L + store.G.C)}</b> edges`;
      $('#issueN').textContent = fmt(store.G.BYST[1] + store.G.BYST[2]);
      renderLegend();
      renderPerf();
      renderRoute();
      renderAttn();
      const B = store.G.bounds,
        t = fitBox(B.x0, B.y0, B.x1, B.y1, 1e-4, 2.2);
      store.KMIN = t.k * 0.5;
      store.KMAX = Math.max(14, t.k * 4);
      const c = viewCenter(),
        wx = (c.x - t.x) / t.k,
        wy = (c.y - t.y) / t.k;
      cam.k = t.k * 0.88;
      cam.x = c.x - wx * cam.k;
      cam.y = c.y - wy * cam.k;
      store.introT0 = performance.now();
      store.introP = 0;
      flyTo(t, 600);
      store.whereKey = '';
      BLD.classList.remove('on');
      if (state) applyHashState(state);
      else writeHash();
      if (hadState && !state)
        toast(
          `Switched to ${n === 'self' ? 'Atlas’s own code' : fmt(n) + ' nodes'}. Selection and route were cleared.`,
        );
      else announce(`Showing ${fmt(store.G.N)} nodes and ${fmt(store.G.L + store.G.C)} edges.`);
    });
  }, 30);
}
export function resize() {
  const r = ov.getBoundingClientRect(),
    oW = store.W,
    oH = store.H;
  store.W = r.width;
  store.H = r.height;
  store.dpr = Math.min(2, devicePixelRatio || 1);
  for (const c of [glc, ov]) {
    c.width = Math.round(store.W * store.dpr);
    c.height = Math.round(store.H * store.dpr);
  }
  if (oW) {
    cam.x += (store.W - oW) / 2;
    cam.y += (store.H - oH) / 2;
  }
  store.placeDirty = true;
  if (store.G) requestRender();
  syncThumb($('#seg'));
  syncThumb($('#scale'));
}
export const mq = matchMedia('(prefers-color-scheme: dark)');
export const onTheme = () => {
  readTheme();
  if (!store.G) return;
  recolor();
  if (store.focusId >= 0) {
    const f = store.focusId;
    store.focusId = -1;
    if (f === ROUTE_FOCUS) computeRouteFocus();
    else computeFocus(f);
    store.focusId = f;
  }
  if (route.path.length) computeRoute();
  renderLegend();
  renderAttn();
  renderRoute();
  if (store.selectedId >= 0) openInspector(store.selectedId);
};
