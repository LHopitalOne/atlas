/**
 * Scene build: geometry for every GPU layer, built once per dataset, plus recolouring for colour mode and issues.
 */
import { stOn, store } from '../state.js';
import { requestRender } from './frame.js';
import { LY, patch, upload } from './gl.js';
import { buildMinimap } from './minimap.js';
import { mixc, nodeCol, put4, theme } from './theme.js';
import { clamp } from '../util/math.js';

/** Territory fill: a triangle fan from the territory centre to each hull edge. */
function fillGeometry(lvl, hulls, cx, cy) {
  let nv = 0;
  for (const h of hulls) nv += (h.length / 2) * 3;
  const pos = new Float32Array(nv * 2),
    col = new Uint8Array(nv * 4),
    owner = new Uint32Array(nv);
  let v = 0;
  hulls.forEach((h, id) => {
    const m = h.length / 2;
    for (let i = 0; i < m; i++) {
      const j = (i + 1) % m;
      pos.set([cx[id], cy[id], h[i * 2], h[i * 2 + 1], h[j * 2], h[j * 2 + 1]], v * 2);
      owner[v] = owner[v + 1] = owner[v + 2] = id;
      v += 3;
    }
  });
  return { pos, col, owner, n: nv, lvl };
}

/** Territory outline: one straight segment per hull edge, width w. */
function outlineGeometry(hulls, w) {
  let n = 0;
  for (const h of hulls) n += h.length / 2;
  const seg = new Float32Array(n * 4),
    prm = new Float32Array(n * 4),
    col = new Uint8Array(n * 4),
    owner = new Uint32Array(n);
  let e = 0;
  hulls.forEach((h, id) => {
    const m = h.length / 2;
    for (let i = 0; i < m; i++) {
      const j = (i + 1) % m;
      seg.set([h[i * 2], h[i * 2 + 1], h[j * 2], h[j * 2 + 1]], e * 4);
      prm.set([w, 0, 0, 4], e * 4);
      owner[e] = id;
      e++;
    }
  });
  return { seg, prm, col, owner, n };
}

/** Vertical extent [top, bottom] of a flat hull (drives the vertical fade). */
function yRange(h) {
  let a = 1e9,
    b = -1e9;
  for (let i = 1; i < h.length; i += 2) {
    if (h[i] < a) a = h[i];
    if (h[i] > b) b = h[i];
  }
  return [a, b];
}

/** Aggregated links between territories or services, drawn as one curve per pair. */
function bundleGeometry(agg, X, Y, curv) {
  const n = agg.n,
    seg = new Float32Array(n * 4),
    prm = new Float32Array(n * 4),
    col = new Uint8Array(n * 4);
  for (let p = 0; p < n; p++) {
    const a = agg.a[p],
      b = agg.b[p];
    seg[p * 4] = X[a];
    seg[p * 4 + 1] = Y[a];
    seg[p * 4 + 2] = X[b];
    seg[p * 4 + 3] = Y[b];
    prm[p * 4 + 1] = curv;
    prm[p * 4 + 3] = 4;
  }
  return { seg, prm, col, n, agg };
}

/** At coarse zoom keep each territory's strongest links plus the busiest tenth overall. */
function backbone(agg, nEnt, topK, minEnt) {
  const keep = new Uint8Array(agg.n);
  if (nEnt <= minEnt) {
    keep.fill(1);
    return keep;
  }
  const tot = new Uint32Array(agg.n);
  for (let p = 0; p < agg.n; p++) tot[p] = agg.c[p * 4] + agg.c[p * 4 + 1] + agg.c[p * 4 + 2] + agg.c[p * 4 + 3];
  const cut = Float64Array.from(tot).sort()[Math.floor(agg.n * 0.9)];
  const per = Array.from({ length: nEnt }, () => []);
  for (let p = 0; p < agg.n; p++) {
    if (tot[p] >= cut) keep[p] = 1;
    per[agg.a[p]].push(p);
    per[agg.b[p]].push(p);
  }
  for (const l of per) {
    l.sort((x, y) => tot[y] - tot[x]);
    for (let i = 0; i < Math.min(topK, l.length); i++) keep[l[i]] = 1;
  }
  return keep;
}

/** Instances for nodes lo..hi-1: position, radius, shape (0 circle, 1 diamond, 2 square, 3 service). */
function nodeGeometry(g, lo, hi) {
  const n = hi - lo,
    d = new Float32Array(n * 4),
    col = new Uint8Array(n * 4),
    fl = new Uint8Array(n * 2);
  for (let i = lo; i < hi; i++) {
    const j = i - lo;
    d[j * 4] = g.PX[i];
    d[j * 4 + 1] = g.PY[i];
    d[j * 4 + 2] = g.PR[i];
    d[j * 4 + 3] = i < g.S ? 3 : g.KND[i] === 2 ? 1 : g.KND[i] === 3 ? 2 : 0;
    fl[j * 2 + 1] = g.REL[i] ? 255 : 0;
  }
  return { d, col, fl, n, lo };
}

/** Upload an edge layer and count its bytes. */
function uploadEdges(L, a) {
  L.n = a.n;
  upload(L, 0, a.seg);
  upload(L, 1, a.prm);
  upload(L, 2, a.col);
  store.gpuBytes += a.seg.byteLength + a.prm.byteLength + a.col.byteLength;
}

/** Upload a node layer and count its bytes. */
function uploadNodes(L, a) {
  L.n = a.n;
  upload(L, 0, a.d);
  upload(L, 1, a.col);
  upload(L, 2, a.fl);
  store.gpuBytes += a.d.byteLength + a.col.byteLength + a.fl.byteLength;
}

/** Upload a fill layer and count its bytes. */
function uploadFills(L, a) {
  L.n = a.n;
  upload(L, 0, a.pos);
  upload(L, 1, a.col);
  store.gpuBytes += a.pos.byteLength + a.col.byteLength;
}

/** Every contract as its own curve; inferred contracts are dashed. */
function contractGeometry(g) {
  const n = g.C,
    seg = new Float32Array(n * 4),
    prm = new Float32Array(n * 4),
    col = new Uint8Array(n * 4);
  for (let e = 0; e < n; e++) {
    const a = g.CS[e],
      b = g.CD[e];
    seg[e * 4] = g.PX[a];
    seg[e * 4 + 1] = g.PY[a];
    seg[e * 4 + 2] = g.PX[b];
    seg[e * 4 + 3] = g.PY[b];
    prm[e * 4] = 1.05;
    prm[e * 4 + 1] = 0.13;
    prm[e * 4 + 2] = g.CST[e] === 3 ? 1 : 0;
    prm[e * 4 + 3] = g.CST[e];
  }
  return { seg, prm, col, n };
}

/** Build every GPU layer for the current graph (once per dataset) and upload it. Returns the time taken in ms. */
export function buildScene() {
  const g = store.G,
    t0 = performance.now();
  store.gpuBytes = 0;
  store.A.repoFill = fillGeometry('r', g.rHull, g.rx, g.ry);
  store.A.domFill = fillGeometry('d', g.dHull, g.dcx, g.dcy);
  store.A.repoLine = outlineGeometry(g.rHull, 0.8);
  store.A.domLine = outlineGeometry(g.dHull, 0.6);
  store.A.rBox = g.rHull.map(yRange);
  store.A.dBox = g.dHull.map(yRange);
  store.A.repoB = bundleGeometry(g.rp, g.rx, g.ry, 0.14);
  store.A.domB = bundleGeometry(g.dp, g.dcx, g.dcy, 0.12);
  store.A.svcB = bundleGeometry(g.sp, g.PX, g.PY, 0.1);
  store.A.repoB.keep = backbone(g.rp, g.R, 3, 12);
  store.A.domB.keep = backbone(g.dp, g.D, 3, 60);
  store.A.leafE = contractGeometry(g);
  store.A.svcs = nodeGeometry(g, 0, g.S);
  store.A.leaves = nodeGeometry(g, g.S, g.N);
  uploadFills(LY.repoFill, store.A.repoFill);
  uploadFills(LY.domFill, store.A.domFill);
  uploadEdges(LY.repoLine, store.A.repoLine);
  uploadEdges(LY.domLine, store.A.domLine);
  uploadEdges(LY.repoB, store.A.repoB);
  uploadEdges(LY.domB, store.A.domB);
  uploadEdges(LY.svcB, store.A.svcB);
  uploadEdges(LY.leafE, store.A.leafE);
  uploadNodes(LY.svcs, store.A.svcs);
  uploadNodes(LY.leaves, store.A.leaves);
  LY.focusE.n = 0;
  LY.route.n = 0;
  LY.routeCase.n = 0;
  recolor();
  return performance.now() - t0;
}
export function recolor() {
  if (!store.G) return;
  const g = store.G,
    dk = theme.dark,
    tint = store.colorMode === 'repo';
  for (const [a, L] of [
    [store.A.svcs, LY.svcs],
    [store.A.leaves, LY.leaves],
  ]) {
    for (let j = 0; j < a.n; j++) put4(a.col, j, nodeCol(a.lo + j), 1);
    patch(L, 1, a.col);
  }
  // vertical fade: full at a territory's top edge, ~10% at its bottom (Vercel-style gradient borders)
  const vf = (y, b) => 1 - 0.9 * clamp((y - b[0]) / Math.max(1, b[1] - b[0]), 0, 1);
  {
    const a = store.A.repoFill;
    for (let v = 0; v < a.n; v++) {
      const r = a.owner[v],
        top = tint && store.repoRank[r] < 5,
        f = vf(a.pos[v * 2 + 1], store.A.rBox[r]);
      put4(
        a.col,
        v,
        top ? theme.pal[store.repoRank[r]] : theme.text,
        (top ? (dk ? 0.07 : 0.06) : dk ? 0.04 : 0.03) * f,
      );
    }
    patch(LY.repoFill, 1, a.col);
  }
  {
    const a = store.A.domFill;
    for (let v = 0; v < a.n; v++) {
      const f = vf(a.pos[v * 2 + 1], store.A.dBox[a.owner[v]]);
      put4(a.col, v, theme.text, (dk ? 0.035 : 0.03) * f);
    }
    patch(LY.domFill, 1, a.col);
  }
  {
    const a = store.A.repoLine;
    for (let e = 0; e < a.n; e++) {
      const r = a.owner[e],
        top = tint && store.repoRank[r] < 5,
        f = vf((a.seg[e * 4 + 1] + a.seg[e * 4 + 3]) / 2, store.A.rBox[r]);
      put4(a.col, e, top ? theme.pal[store.repoRank[r]] : theme.text, (top ? 0.5 : dk ? 0.22 : 0.2) * f);
    }
    patch(LY.repoLine, 2, a.col);
  }
  {
    const a = store.A.domLine;
    for (let e = 0; e < a.n; e++) {
      const f = vf((a.seg[e * 4 + 1] + a.seg[e * 4 + 3]) / 2, store.A.dBox[a.owner[e]]);
      put4(a.col, e, theme.text, (dk ? 0.13 : 0.11) * f);
    }
    patch(LY.domLine, 2, a.col);
  }
  {
    const a = store.A.leafE,
      cs = [
        [theme.edge, theme.edge[3]],
        [theme.st[1], 0.62],
        [theme.st[2], 0.62],
        [theme.st[3], 0.55],
      ];
    for (let e = 0; e < a.n; e++) {
      const c = cs[g.CST[e]];
      put4(a.col, e, c[0], c[1]);
    }
    patch(LY.leafE, 2, a.col);
  }
  bundleStyle();
  buildMinimap();
  requestRender();
}
// Bundles behave like a road hierarchy: width and opacity follow traffic; colour flags only links worse than typical for their level
export function bundleStyle() {
  const mask = [stOn[0] && !store.issuesOnly, stOn[1], stOn[2], stOn[3] && !store.issuesOnly];
  for (const [a, L, w0, wk, wmax] of [
    [store.A.repoB, LY.repoB, 0.7, 0.07, 1.6],
    [store.A.domB, LY.domB, 0.7, 0.08, 1.4],
    [store.A.svcB, LY.svcB, 0.7, 0.12, 1.3],
  ]) {
    const c = a.agg.c;
    let mx = 1,
      im = 0,
      it = 0;
    for (let p = 0; p < a.n; p++) {
      const t = c[p * 4] + c[p * 4 + 1] + c[p * 4 + 2] + c[p * 4 + 3];
      if (t > mx) mx = t;
      im += c[p * 4 + 1] * 0.5 + c[p * 4 + 2];
      it += c[p * 4] + c[p * 4 + 1] + c[p * 4 + 2];
    }
    const base = store.issuesOnly ? 0 : it ? im / it : 0;
    for (let p = 0; p < a.n; p++) {
      const m = mask[0] ? c[p * 4] : 0,
        am = mask[1] ? c[p * 4 + 1] : 0,
        u = mask[2] ? c[p * 4 + 2] : 0,
        f = mask[3] ? c[p * 4 + 3] : 0,
        tot = m + am + u + f;
      if (!tot || (a.keep && !a.keep[p])) {
        a.prm[p * 4] = 0;
        a.col[p * 4 + 3] = 0;
        continue;
      }
      const share = Math.sqrt(tot / mx);
      a.prm[p * 4] = Math.min(wmax, w0 + wk * Math.sqrt(tot));
      if (m + am + u === 0) {
        a.prm[p * 4 + 2] = 1;
        put4(a.col, p, theme.st[3], 0.15 + 0.3 * share);
        continue;
      }
      a.prm[p * 4 + 2] = 0;
      const r = (am * 0.5 + u) / (m + am + u),
        t = clamp((r - base) / (0.6 - base * 0.5), 0, 1);
      const col = t < 0.5 ? mixc(theme.text, theme.st[1], t * 2) : mixc(theme.st[1], theme.st[2], (t - 0.5) * 2);
      put4(a.col, p, col, (0.06 + 0.5 * share) * (1 - t) + (0.35 + 0.5 * share) * t);
    }
    patch(L, 1, a.prm);
    patch(L, 2, a.col);
  }
}
