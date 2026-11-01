/**
 * The 2D overlay drawn above the WebGL map: outlines, flow dots, rings, pins, edge chips, reticle and labels.
 * drawOverlay builds a per-frame context and runs each pass in order; label placement lives in labels.js.
 */
import { cam, route, stOn, store } from '../state.js';
import { safeRect, viewCenter } from '../app/camera.js';
import { ASK_FOCUS, ROUTE_FOCUS, routeActive } from '../app/focus.js';
import { endPoint } from '../app/route.js';
import { oc } from '../dom.js';
import { scrR } from './frame.js';
import { css, theme } from './theme.js';
import { LC, rrect, tw } from './canvas.js';
import { drawLabels } from './labels.js';
import { reduceMotion } from '../util/dom.js';
import { fmt, SANS } from '../util/format.js';
import { clamp } from '../util/math.js';

/**
 * @typedef {{g:object, k:number, I:number, now:number, V:object, SX:(x:number)=>number, SY:(y:number)=>number,
 *   on:(x:number,y:number,m?:number)=>boolean, sel:boolean, hasF:boolean, dimF:number}} FrameCtx
 */

/** Draw the overlay for one frame. */
export function drawOverlay(now, V, I) {
  const g = store.G,
    k = cam.k,
    sel = store.selectedId >= 0,
    hasF = store.focusId >= 0 && store.focusT > 0.001,
    dimF = 1 - 0.86 * store.dimT;
  oc.setTransform(store.dpr, 0, 0, store.dpr, 0, 0);
  oc.clearRect(0, 0, store.W, store.H);
  oc.textBaseline = 'middle';
  oc.lineJoin = 'round';
  const SX = x => x * k + cam.x,
    SY = y => y * k + cam.y,
    on = (x, y, m = 40) => x > -m && x < store.W + m && y > -m && y < store.H + m;
  LC.reset(store.W, store.H);
  store.offHits = [];
  const fx = { g, k, I, now, V, SX, SY, on, sel, hasF, dimF };
  drawTerritoryHover(fx);
  drawSelectionFlow(fx);
  drawRouteFlow(fx);
  drawRings(fx);
  const pins = drawRoutePins(fx);
  drawOffscreenChips(fx);
  drawReticle(fx);
  drawLabels(fx, pins);
  oc.globalAlpha = 1;
}

/** Outline the territory under the pointer. */
function drawTerritoryHover(fx) {
  const { g, SX, SY } = fx;
  if (store.hover && (store.hover.t === 'd' || store.hover.t === 'r')) {
    const h = store.hover.t === 'd' ? g.dHull[store.hover.id] : g.rHull[store.hover.id];
    oc.beginPath();
    for (let i = 0; i < h.length; i += 2) oc.lineTo(SX(h[i]), SY(h[i + 1]));
    oc.closePath();
    oc.globalAlpha = 1;
    oc.lineWidth = 1.5;
    oc.strokeStyle = css(theme.text, 0.45);
    oc.stroke();
    oc.fillStyle = css(theme.text, 0.03);
    oc.fill();
  }
}

/** Dots travelling along the selected item's contracts, in call direction. */
function drawSelectionFlow(fx) {
  const { g, I, now, SX, SY, on, sel } = fx;
  // flow along a selected item's contracts
  if (sel && store.dimT > 0.02 && store.focusEdges.length && store.focusEdges.length <= 900) {
    const tt = now * 0.00038;
    for (const e of store.focusEdges) {
      const st = g.CST[e];
      if (!stOn[st] || (store.issuesOnly && (st === 0 || st === 3))) continue;
      const a = g.CS[e],
        b = g.CD[e],
        x0 = g.PX[a],
        y0 = g.PY[a],
        x1 = g.PX[b],
        y1 = g.PY[b],
        dx = x1 - x0,
        dy = y1 - y0,
        cx = (x0 + x1) / 2 - dy * 0.13,
        cy = (y0 + y1) / 2 + dx * 0.13;
      oc.fillStyle = st === 0 ? css(theme.text) : css(theme.st[st]);
      for (let q = 0; q < (reduceMotion ? 1 : 2); q++) {
        const t = reduceMotion ? 0.78 : (tt + ((e * 0.6180339) % 1) + q * 0.5) % 1,
          u = 1 - t;
        const x = SX(u * u * x0 + 2 * u * t * cx + t * t * x1),
          y = SY(u * u * y0 + 2 * u * t * cy + t * t * y1);
        if (!on(x, y, 4)) continue;
        oc.globalAlpha = I * store.dimT * (reduceMotion ? 1 : Math.sin(Math.PI * t) * 0.95);
        oc.beginPath();
        oc.arc(x, y, 2.1, 0, Math.PI * 2);
        oc.fill();
      }
    }
  }
}

/** Dots travelling along the route (start to destination) or an answer's trail (in reading order). */
function drawRouteFlow(fx) {
  const { g, k, I, now, SX, SY, on } = fx;
  // flow along the route (start to destination), or along an answer's trail (in reading order)
  const hops =
    store.focusId === ROUTE_FOCUS && routeActive()
      ? route.hops
      : store.focusId === ASK_FOCUS && store.askSet.length
        ? store.askHops
        : null;
  if (hops && hops.length && store.dimT > 0.02 && !reduceMotion) {
    oc.lineWidth = 1;
    oc.strokeStyle = css(theme.halo);
    oc.fillStyle = css(theme.route);
    for (const h of hops) {
      const x0 = g.PX[h.a],
        y0 = g.PY[h.a],
        x1 = g.PX[h.b],
        y1 = g.PY[h.b],
        dx = x1 - x0,
        dy = y1 - y0,
        cx = (x0 + x1) / 2 - dy * 0.1,
        cy = (y0 + y1) / 2 + dx * 0.1;
      const L = Math.hypot(dx, dy) * k,
        n = Math.max(1, Math.min(5, Math.round(L / 120)));
      for (let q = 0; q < n; q++) {
        const t = ((now * 0.09) / Math.max(L, 1) + q / n) % 1,
          u = 1 - t;
        const x = SX(u * u * x0 + 2 * u * t * cx + t * t * x1),
          y = SY(u * u * y0 + 2 * u * t * cy + t * t * y1);
        if (!on(x, y, 6)) continue;
        oc.globalAlpha = I * store.dimT * Math.min(1, Math.sin(Math.PI * t) * 2.2);
        oc.beginPath();
        oc.arc(x, y, 2.2, 0, Math.PI * 2);
        oc.stroke();
        oc.fill();
      }
    }
  }
}

/** Rings around the selected and hovered nodes, and the highlighted route step. */
function drawRings(fx) {
  const { g, I, SX, SY } = fx;
  // rings
  for (const [id, w, al] of [
    [store.selectedId, 1.8, 1],
    [store.hover && store.hover.t === 'n' ? store.hover.id : -1, 1.4, 0.6],
  ]) {
    if (id < 0 || (al < 1 && id === store.selectedId)) continue;
    oc.globalAlpha = al * I;
    oc.strokeStyle = css(theme.text);
    oc.lineWidth = w;
    oc.beginPath();
    oc.arc(SX(g.PX[id]), SY(g.PY[id]), scrR(id) + (id < g.S ? 4.5 : 3.5), 0, Math.PI * 2);
    oc.stroke();
  }
  // highlighted route step
  if (route.hl >= 0 && route.hops[route.hl]) {
    const h = route.hops[route.hl];
    for (const s of [h.a, h.b]) {
      oc.globalAlpha = 1;
      oc.strokeStyle = css(theme.route);
      oc.lineWidth = 2.5;
      oc.beginPath();
      oc.arc(SX(g.PX[s]), SY(g.PY[s]), scrR(s) + 7, 0, Math.PI * 2);
      oc.stroke();
    }
  }
}

/** Start and destination markers. Returns them so their labels can be reserved. */
function drawRoutePins(fx) {
  const { I, SX, SY } = fx;
  // route pins
  const pins = [];
  if (route.from) pins.push([route.from, 'a']);
  if (route.to) pins.push([route.to, 'b']);
  for (const [end, t] of pins) {
    const [wx, wy] = endPoint(end),
      x = SX(wx),
      y = SY(wy);
    oc.globalAlpha = I;
    if (t === 'a') {
      oc.beginPath();
      oc.arc(x, y, 5.5, 0, Math.PI * 2);
      oc.fillStyle = css(theme.halo);
      oc.fill();
      oc.lineWidth = 1.6;
      oc.strokeStyle = css(theme.route);
      oc.stroke();
      oc.beginPath();
      oc.arc(x, y, 1.8, 0, Math.PI * 2);
      oc.fillStyle = css(theme.route);
      oc.fill();
    } else {
      const r = 9,
        cy = y - r * 2.2;
      oc.beginPath();
      oc.moveTo(x, y);
      oc.bezierCurveTo(x - r * 0.35, cy + r * 1.2, x - r, cy + r * 0.5, x - r, cy);
      oc.arc(x, cy, r, Math.PI, 0);
      oc.bezierCurveTo(x + r, cy + r * 0.5, x + r * 0.35, cy + r * 1.2, x, y);
      oc.closePath();
      oc.fillStyle = css(theme.text);
      oc.fill();
      oc.lineWidth = 1.5;
      oc.strokeStyle = css(theme.halo);
      oc.stroke();
      oc.beginPath();
      oc.arc(x, cy, 3.2, 0, Math.PI * 2);
      oc.fillStyle = css(theme.halo);
      oc.fill();
    }
  }
  return pins;
}

/** Edge chips counting the selection's off-screen neighbours; also click targets. */
function drawOffscreenChips(fx) {
  const { g, I, SX, SY, sel } = fx;
  // off-screen connections of the selection, grouped by direction like map edge markers
  if (sel && store.dimT > 0.3) {
    const R = safeRect(),
      cx = (R.l + R.r) / 2,
      cy = (R.t + R.b) / 2,
      own = g.own(store.selectedId),
      bins = new Map();
    for (const i of store.focusList) {
      if (i >= g.S || i === own) continue;
      const x = SX(g.PX[i]),
        y = SY(g.PY[i]);
      if (x >= R.l && x <= R.r && y >= R.t && y <= R.b) continue;
      const a = Math.atan2(y - cy, x - cx),
        s = Math.round(a / (Math.PI / 6));
      let o = bins.get(s);
      if (!o) {
        o = { ids: [], vx: 0, vy: 0 };
        bins.set(s, o);
      }
      o.ids.push(i);
      o.vx += Math.cos(a);
      o.vy += Math.sin(a);
    }
    oc.font = '500 12px ' + SANS;
    for (const o of bins.values()) {
      const a = Math.atan2(o.vy, o.vx),
        dx = Math.cos(a),
        dy = Math.sin(a);
      const t = Math.min(
        dx > 0 ? (R.r - cx) / dx : dx < 0 ? (R.l - cx) / dx : 1e9,
        dy > 0 ? (R.b - cy) / dy : dy < 0 ? (R.t - cy) / dy : 1e9,
      );
      const label = fmt(o.ids.length),
        w = tw('500 12px ' + SANS, label) + 30,
        h = 26;
      const px = clamp(cx + dx * t - w / 2, R.l, R.r - w),
        py = clamp(cy + dy * t - h / 2, R.t, R.b - h);
      oc.globalAlpha = I * store.dimT;
      rrect(px, py, w, h, 13);
      oc.fillStyle = css(theme.halo);
      oc.fill();
      oc.lineWidth = 1;
      oc.strokeStyle = css(theme.text, 0.25);
      oc.stroke();
      // arrow pointing toward the hidden neighbours
      const ax = px + 13,
        ay = py + h / 2;
      oc.save();
      oc.translate(ax, ay);
      oc.rotate(a);
      oc.beginPath();
      oc.moveTo(5, 0);
      oc.lineTo(-3, -4.5);
      oc.lineTo(-3, 4.5);
      oc.closePath();
      oc.fillStyle = css(theme.text);
      oc.fill();
      oc.restore();
      oc.fillStyle = css(theme.text);
      oc.textAlign = 'left';
      oc.fillText(label, px + 22, ay);
      store.offHits.push({ x0: px, y0: py, x1: px + w, y1: py + h, ids: o.ids });
      LC.fits(px, py, px + w, py + h, true);
    }
  }
}

/** Centre marker shown while the map has keyboard focus. */
function drawReticle(fx) {
  // keyboard reticle
  if (store.kbdMap) {
    const c = viewCenter();
    oc.globalAlpha = 0.9;
    oc.strokeStyle = css(theme.text);
    oc.lineWidth = 1.5;
    oc.beginPath();
    oc.arc(c.x, c.y, 12, 0, Math.PI * 2);
    for (const [ax, ay] of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ]) {
      oc.moveTo(c.x + ax * 16, c.y + ay * 16);
      oc.lineTo(c.x + ax * 22, c.y + ay * 22);
    }
    oc.stroke();
  }
}
