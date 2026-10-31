/**
 * Map labels, following the Google Maps / Mapbox model: fixed-size text anchored to points on the map.
 * A placement pass decides which labels show (greedy by priority, no collisions); it runs at most every 250 ms
 * while the camera moves and once more when it settles. Between passes, placed labels ride along with the map,
 * and each label fades in or out on its own clock instead of popping or reshuffling.
 *
 * Label keys: 'r<repo>', 'd<domain>', 's<service>', 'l<leaf>'.
 */
import { cam, store } from '../state.js';
import { requestRender, scrR } from './frame.js';
import { css, mixc, theme } from './theme.js';
import { LC, text, tw } from './canvas.js';
import { reduceMotion } from '../util/dom.js';
import { MONO, SANS } from '../util/format.js';
import { clamp, easeOut } from '../util/math.js';
import { LABELS } from '../config.js';

let prevLabels = new Set();
let lastPlace = 0;
let placeCam = { x: NaN, y: NaN, k: NaN };
let placeTO = 0;
let labelT = 0;
let lastHide = false;
/** Order candidates so labels shown last pass keep priority (hysteresis against flicker). */
const stable = (arr, key) => {
  const a = [],
    b = [];
  for (const x of arr) (prevLabels.has(key(x)) ? a : b).push(x);
  return a.length ? a.concat(b) : arr;
};

const FS = '500 12px ' + SANS,
  FSB = '600 12.5px ' + SANS,
  FL = '400 10.5px ' + MONO,
  FR = '600 15px ' + SANS,
  FD = '500 12px ' + SANS;

/** Screen geometry for a label key: anchor, text, font, and (except services) its collision box. */
function labelGeometry(fx, key) {
  const { g, SX, SY } = fx;
  const t = key[0],
    id = +key.slice(1);
  if (t === 'r' || t === 'd') {
    const isR = t === 'r',
      nm = isR ? g.repoName[id] : g.domName[id],
      font = isR ? FR : FD,
      w = tw(font, nm),
      x = SX(isR ? g.rx[id] : g.dcx[id]),
      y = SY(isR ? g.ry[id] : g.dcy[id]);
    return { t, id, x, y, w, nm, font, align: 'center', box: [x - w / 2 - 4, y - 10, x + w / 2 + 4, y + 10] };
  }
  if (t === 's') {
    const rr = scrR(id),
      x = SX(g.PX[id]),
      y = SY(g.PY[id]),
      nm = g.svcName[id];
    return { t, id, x, y, rr, nm, font: FS, w: tw(FS, nm) };
  }
  const p = g.own(id),
    x = SX(g.PX[id]),
    y = SY(g.PY[id]),
    ang = Math.atan2(g.PY[id] - g.PY[p], g.PX[id] - g.PX[p]),
    c = Math.cos(ang),
    sn = Math.sin(ang);
  const nm = g.name(id),
    w = tw(FL, nm),
    gap = scrR(id) + 5,
    lx = x + c * gap,
    ly = y + sn * gap * 0.6,
    right = c >= 0;
  return {
    t,
    id,
    x: lx,
    y: ly,
    w,
    nm,
    font: FL,
    align: right ? 'left' : 'right',
    box: [right ? lx - 2 : lx - w - 2, ly - 7, right ? lx + w + 2 : lx + 2, ly + 7],
  };
}
/** Collision box for a service label on the given side of its disc. */
const svcBox = (q, side) =>
  side === 'right'
    ? [q.x + q.rr + 6, q.y - 8, q.x + q.rr + 10 + q.w, q.y + 8]
    : [q.x - q.rr - 10 - q.w, q.y - 8, q.x - q.rr - 6, q.y + 8];

/** Pinned labels (selection, hover, route ends) always show; their space is reserved first. */
function reservePinned(fx, pins) {
  const { g } = fx;
  const geo = key => labelGeometry(fx, key);
  const pinned = [];
  if (store.selectedId >= 0) pinned.push((store.selectedId < g.S ? 's' : 'l') + store.selectedId);
  if (store.hover) {
    if (store.hover.t === 'n') pinned.push((store.hover.id < g.S ? 's' : 'l') + store.hover.id);
    else pinned.push(store.hover.t + store.hover.id);
  }
  for (const [end] of pins) pinned.push(end.t + end.id);
  const pinnedSet = new Set(pinned);
  for (const key of pinned) {
    const q = geo(key);
    const b = q.t === 's' ? svcBox(q, store.labelSide.get(key) || 'right') : q.box;
    LC.fits(b[0], b[1], b[2], b[3], true);
  }
  return { pinned, pinnedSet };
}

/** Is a placement pass due? Throttled while the camera moves, plus one pass once it settles. */
function placementDue(now, hideOthers) {
  if (hideOthers !== lastHide) {
    lastHide = hideOthers;
    store.placeDirty = true;
  }
  const moved = cam.x !== placeCam.x || cam.y !== placeCam.y || cam.k !== placeCam.k;
  if (moved) {
    clearTimeout(placeTO);
    placeTO = setTimeout(() => {
      store.placeDirty = true;
      requestRender();
    }, LABELS.settleMs);
  }
  return store.placeDirty || (moved && now - lastPlace > LABELS.throttleMs);
}

/** Decide which labels show, tier by tier, without collisions. Runs only when placement is due. */
function placeLabels(fx, pinnedSet) {
  const hideOthers = store.dimT > 0.5;
  if (!placementDue(fx.now, hideOthers)) return;
  prevLabels = new Set(store.placed.keys());
  const next = new Map();
  const put = (key, b, side) => {
    if (!LC.fits(b[0], b[1], b[2], b[3], false)) return false;
    next.set(key, 1);
    if (side) store.labelSide.set(key, side);
    return true;
  };
  const pc = { ...fx, put, hideOthers, pinnedSet, geo: key => labelGeometry(fx, key) };
  if (fx.V.aRL > 0.5 && !hideOthers) placeRepoLabels(pc);
  if (fx.V.aDL > 0.5 && !hideOthers) placeDomainLabels(pc);
  if (fx.V.svcA > 0.4) placeServiceLabels(pc);
  if (fx.k >= LABELS.leafZoom || (hideOthers && fx.k >= LABELS.focusLeafZoom)) placeLeafLabels(pc);
  store.placed = next;
  lastPlace = fx.now;
  placeCam = { x: cam.x, y: cam.y, k: cam.k };
  store.placeDirty = false;
}

/** Tier 1: repositories (countries). A name shows only once it fits inside its territory. */
function placeRepoLabels({ g, k, on, put, geo }) {
  let n = 0;
  for (const r of stable(g.repoOrder, x => 'r' + x)) {
    const q = geo('r' + r);
    if (g.rR[r] * k * 2 < q.w * 0.7 || !on(q.x, q.y, q.w)) continue;
    if (put('r' + r, q.box) && ++n > LABELS.caps.repo) break;
  }
}

/** Tier 2: domains (states). */
function placeDomainLabels({ g, k, on, put, geo }) {
  let n = 0;
  for (const d of stable(g.domOrder, x => 'd' + x)) {
    const rr = g.dR[d] * k;
    if (rr < 22) continue;
    const q = geo('d' + d);
    if (rr * 2 < q.w * 1.05 || !on(q.x, q.y, q.w)) continue;
    if (put('d' + d, q.box) && ++n > LABELS.caps.domain) break;
  }
}

/** Tier 3: services (cities). Their discs become obstacles first, so a name never covers a service. */
function placeServiceLabels({ g, k, SX, SY, on, put, geo, hideOthers, pinnedSet }) {
  if (g.medRF * k >= 11)
    for (let s = 0; s < g.S; s++) {
      const x = SX(g.PX[s]),
        y = SY(g.PY[s]),
        r = scrR(s) + 1.5;
      if (on(x, y)) LC.fits(x - r, y - r, x + r, y + r, true);
    }
  const minR = hideOthers ? 0 : 13;
  let n = 0;
  for (const s of stable(g.svcOrder, x => 's' + x)) {
    if (g.RF[s] * k < minR || (hideOthers && !store.inF[s]) || pinnedSet.has('s' + s)) continue;
    const q = geo('s' + s);
    if (!on(q.x, q.y)) continue;
    const pref = store.labelSide.get('s' + s) || 'right',
      alt = pref === 'right' ? 'left' : 'right';
    if ((put('s' + s, svcBox(q, pref), pref) || put('s' + s, svcBox(q, alt), alt)) && ++n > LABELS.caps.service) break;
  }
}

/** Endpoints inside the viewport, read from the static spatial grid. */
function leavesInView(g, k, hideOthers) {
  const gr = g.grid,
    out = [],
    cellOf = v => Math.floor(v / gr.CELL);
  const c0 = clamp(cellOf(-cam.x / k - gr.x0), 0, gr.GC - 1),
    c1 = clamp(cellOf((store.W - cam.x) / k - gr.x0), 0, gr.GC - 1);
  const r0 = clamp(cellOf(-cam.y / k - gr.y0), 0, gr.GR - 1),
    r1 = clamp(cellOf((store.H - cam.y) / k - gr.y0), 0, gr.GR - 1);
  for (let r = r0; r <= r1; r++)
    for (let c = c0; c <= c1; c++) {
      const id = r * gr.GC + c;
      for (let j = gr.GO[id]; j < gr.GO[id + 1]; j++) {
        const i = gr.GI[j];
        if (i >= g.S && !(hideOthers && !store.inF[i])) out.push(i);
      }
    }
  return out;
}

/** Tier 4: endpoints (streets) at close zoom, or the selection's endpoints when everything else is dimmed. */
function placeLeafLabels({ g, k, on, put, geo, hideOthers, hasF, pinnedSet }) {
  const cand = k >= LABELS.leafZoom ? leavesInView(g, k, hideOthers) : store.focusList.filter(i => i >= g.S);
  cand.sort((a, b) => (hasF && store.inF[b]) - (hasF && store.inF[a]) || g.ISS[b] - g.ISS[a]);
  let n = 0;
  for (const i of stable(cand, x => 'l' + x)) {
    if (pinnedSet.has('l' + i)) continue;
    const q = geo('l' + i);
    if (!on(q.x, q.y, 10)) continue;
    if (put('l' + i, q.box) && ++n > LABELS.caps.leaf) break;
  }
}

/** Ease every label toward its target opacity; fully faded labels are dropped. */
function stepFades(now) {
  const dt = labelT ? Math.min(0.1, (now - labelT) / 1000) : 0;
  labelT = now;
  store.labelsAnimating = false;
  for (const key of store.placed.keys()) if (!store.labelA.has(key)) store.labelA.set(key, 0);
  for (const [key, a0] of store.labelA) {
    const target = store.placed.has(key) ? 1 : 0;
    const a = reduceMotion
      ? target
      : target > a0
        ? Math.min(1, a0 + dt / LABELS.fadeInS)
        : Math.max(0, a0 - dt / LABELS.fadeOutS);
    if (a !== target) store.labelsAnimating = true;
    if (a <= 0 && !target) store.labelA.delete(key);
    else store.labelA.set(key, a);
  }
}

const leafColor = (g, i, base) => (g.ISS[i] === 2 ? theme.st[2] : g.ISS[i] === 1 ? theme.st[1] : base);
function drawServiceText(q, key, font, color, alpha) {
  const side = store.labelSide.get(key) || 'right';
  text(
    q.nm,
    side === 'right' ? q.x + q.rr + 7 : q.x - q.rr - 7,
    q.y,
    side === 'right' ? 'left' : 'right',
    font,
    color,
    alpha,
  );
}

/** A placed label at its current fade. */
function paintFaded(fx, q, key, a) {
  const { g, I, dimF } = fx,
    ea = easeOut(a),
    territoryAlpha = ea * I * (1 - 0.6 * store.dimT);
  if (q.t === 'r') {
    const top = store.colorMode === 'repo' && store.repoRank[q.id] < 5;
    const col = top ? mixc(theme.pal[store.repoRank[q.id]], theme.text, 0.25) : mixc(theme.text, theme.muted, 0.3);
    return text(q.nm, q.x, q.y, 'center', q.font, css(col), territoryAlpha, 4);
  }
  if (q.t === 'd') return text(q.nm, q.x, q.y, 'center', q.font, css(theme.muted), territoryAlpha, 4);
  if (q.t === 's')
    return drawServiceText(
      q,
      key,
      q.font,
      css(theme.text),
      ea * I * (store.dimT > 0 && !store.inF[q.id] ? dimF : 1) * (store.issuesOnly && !g.REL[q.id] ? 0.35 : 1),
    );
  text(
    q.nm,
    q.x,
    q.y,
    q.align,
    q.font,
    css(leafColor(g, q.id, theme.muted)),
    ea * I * (store.issuesOnly && !g.REL[q.id] ? 0.4 : 1),
    3,
  );
}

/** A pinned label: immediate and at full contrast. */
function paintPinned(fx, q, key) {
  const { g, I } = fx;
  if (q.t === 's') {
    const bold = q.id === store.selectedId || (store.hover && store.hover.id === q.id);
    return drawServiceText(q, key, bold ? FSB : FS, css(theme.text), I);
  }
  if (q.t === 'l') return text(q.nm, q.x, q.y, q.align, q.font, css(leafColor(g, q.id, theme.text)), I, 3);
  text(q.nm, q.x, q.y, 'center', q.font, css(theme.text), I, 4);
}

function paintLabels(fx, pinned, pinnedSet) {
  stepFades(fx.now);
  for (const [key, a] of store.labelA) if (!pinnedSet.has(key)) paintFaded(fx, labelGeometry(fx, key), key, a);
  for (const key of pinned) paintPinned(fx, labelGeometry(fx, key), key);
}

/** Reserve pinned labels, place the rest when due, then paint. */
export function drawLabels(fx, pins) {
  const { pinned, pinnedSet } = reservePinned(fx, pins);
  placeLabels(fx, pinnedSet);
  paintLabels(fx, pinned, pinnedSet);
}
