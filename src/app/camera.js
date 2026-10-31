/**
 * Camera: the view transform (cam.x, cam.y, cam.k), fitting, zooming and animated flights.
 * Keyboard-initiated moves are instant; pointer and UI moves use the ease-in-out flight curve.
 */
import { cam, store } from '../state.js';
import { app, ATTN, RT } from '../dom.js';
import { requestRender } from '../render/frame.js';
import { reduceMotion } from '../util/dom.js';
import { clamp, easeMove } from '../util/math.js';

export const inspOpen = () => app.classList.contains('has-insp');
export const leftOpen = () => RT.classList.contains('on') || ATTN.classList.contains('on');
export function viewCenter() {
  const R = safeRect();
  return { x: (R.l + R.r) / 2, y: (R.t + R.b) / 2 };
}
function availWH() {
  const R = safeRect();
  return [Math.max(80, R.r - R.l - 40), Math.max(80, R.b - R.t - (store.W > 760 ? 90 : 40))];
}
export const camFor = (wx, wy, k) => {
  const c = viewCenter();
  return { x: c.x - wx * k, y: c.y - wy * k, k };
};
export function fitBox(x0, y0, x1, y1, kmin = store.KMIN, kmax = store.KMAX) {
  const [aw, ah] = availWH();
  const k = clamp(Math.min(aw / Math.max(1, x1 - x0), ah / Math.max(1, y1 - y0)), kmin, kmax);
  return camFor((x0 + x1) / 2, (y0 + y1) / 2, k);
}
export function fitNodes(list, kmax = 3.2) {
  const g = store.G;
  let x0 = 1e9,
    y0 = 1e9,
    x1 = -1e9,
    y1 = -1e9;
  for (const i of list) {
    const r = g.PR[i] + (i < g.S ? g.RF[i] - g.RS[i] : 4);
    x0 = Math.min(x0, g.PX[i] - r);
    x1 = Math.max(x1, g.PX[i] + r);
    y0 = Math.min(y0, g.PY[i] - r);
    y1 = Math.max(y1, g.PY[i] + r);
  }
  return fitBox(x0, y0, x1, y1, store.KMIN, kmax);
}
export function flyTo(t, dur = 450) {
  if (store.viaKeys) dur = 0;
  const c = viewCenter();
  store.anim = {
    c,
    w0x: (c.x - cam.x) / cam.k,
    w0y: (c.y - cam.y) / cam.k,
    k0: cam.k,
    w1x: (c.x - t.x) / t.k,
    w1y: (c.y - t.y) / t.k,
    k1: t.k,
    t0: performance.now(),
    dur: reduceMotion ? 0 : dur,
  };
  requestRender();
}
export function stepAnim(now) {
  const a = store.anim,
    p = a.dur ? clamp((now - a.t0) / a.dur, 0, 1) : 1,
    e = easeMove(p);
  const dist = Math.hypot(a.w1x - a.w0x, a.w1y - a.w0y) * Math.min(a.k0, a.k1),
    bump = dist > store.W * 0.8 ? Math.log(Math.min(4, dist / (store.W * 0.8))) * Math.sin(Math.PI * e) : 0;
  const k = Math.exp(Math.log(a.k0) + (Math.log(a.k1) - Math.log(a.k0)) * e - bump);
  cam.k = k;
  cam.x = a.c.x - (a.w0x + (a.w1x - a.w0x) * e) * k;
  cam.y = a.c.y - (a.w0y + (a.w1y - a.w0y) * e) * k;
  if (p >= 1) {
    store.anim = null;
    return false;
  }
  return true;
}
export function zoomAt(px, py, f) {
  store.anim = null;
  const k2 = clamp(cam.k * f, store.KMIN, store.KMAX),
    wx = (px - cam.x) / cam.k,
    wy = (py - cam.y) / cam.k;
  cam.k = k2;
  cam.x = px - wx * k2;
  cam.y = py - wy * k2;
  requestRender();
}
export const fitAll = dur => {
  if (!store.G) return;
  const B = store.G.bounds;
  flyTo(fitBox(B.x0, B.y0, B.x1, B.y1), dur);
};
export const flyToTerr = (lvl, id) => {
  const g = store.G,
    cx = lvl === 'r' ? g.rx[id] : g.dcx[id],
    cy = lvl === 'r' ? g.ry[id] : g.dcy[id],
    r = lvl === 'r' ? g.rR[id] : g.dR[id];
  flyTo(fitBox(cx - r, cy - r, cx + r, cy + r));
};

/** The part of the screen not covered by panels: used to centre the camera and place edge markers. */
export function safeRect() {
  const wide = store.W > 760;
  return {
    l: wide && leftOpen() ? 412 : 16,
    r: store.W - 16 - (inspOpen() && wide ? 374 : 0),
    t: store.W > 1040 ? 68 : 112,
    b: store.H - (inspOpen() && !wide ? store.H * 0.5 + 16 : 16),
  };
}
