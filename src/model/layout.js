/**
 * Layout: turns a raw graph (hierarchy + contracts) into positions, territory outlines and lookup indexes.
 * Works on any graph, synthetic or indexed from real code. Deterministic.
 *
 * Geometry, in world units:
 *   service  = disc of radius RS, with its endpoints on concentric rings around it (footprint radius RF)
 *   domain   = circle packing of its services (radius dR)
 *   repo     = circle packing of its domains (radius rR); repos are packed into the world
 * Siblings are ordered by how much they talk to each other before packing, so busy neighbours sit close.
 */
import { clamp } from '../util/math.js';
import { adjacency, aggregates, forwardIndex, pairWeight, statusStats } from './graph-index.js';
import { angDiff, convexHull, hullTop, median } from './geometry.js';

const RING_SPACING = 8.6; // gap between endpoint dots on a ring
const GRID_CELL = 24; // spatial grid cell for hit-testing
const PAD = { service: 6, domain: 16, repo: 22, world: 14, domainHull: 14, repoHull: 30 };
const LEAF_RADIUS = { 1: 2.55, 2: 2.8, 3: 2.35 }; // endpoint, event, module

/** How many endpoints go on each ring around a service of radius rs. */
export function ringPlan(n, rs) {
  let d = rs + 9.5;
  const caps = [],
    ds = [];
  let tot = 0;
  while (tot < n) {
    const cap = Math.max(6, Math.floor((2 * Math.PI * d) / RING_SPACING));
    caps.push(cap);
    ds.push(d);
    tot += cap;
    d += RING_SPACING * 0.95;
  }
  const take = caps.map(c => Math.floor((n * c) / tot));
  let left = n - take.reduce((a, b) => a + b, 0);
  for (let i = caps.length - 1; left > 0; i = (i - 1 + caps.length) % caps.length)
    if (take[i] < caps[i]) {
      take[i]++;
      left--;
    }
  return { ds, take };
}

/**
 * Order siblings so that each next one talks most to those already placed (ties: larger first).
 * @param {number[]} list ids
 * @param {(a:number,b:number)=>number} w traffic between two ids
 * @param {(a:number)=>number} size
 */
export function affinityOrder(list, w, size) {
  if (list.length < 3) return list.slice().sort((a, b) => size(b) - size(a));
  let first = list[0];
  for (const x of list) if (size(x) > size(first)) first = x;
  const out = [first],
    rest = new Set(list);
  rest.delete(first);
  const score = new Map();
  for (const x of rest) score.set(x, w(first, x));
  while (rest.size) {
    let best = -1,
      bv = -1,
      bz = -1;
    for (const x of rest) {
      const v = score.get(x),
        z = size(x);
      if (v > bv || (v === bv && z > bz)) {
        bv = v;
        bz = z;
        best = x;
      }
    }
    out.push(best);
    rest.delete(best);
    for (const x of rest) score.set(x, score.get(x) + w(best, x));
  }
  return out;
}

/** Pack circles with d3 and centre them; returns the enclosing circle. */
function pack(circles) {
  globalThis.d3.packSiblings(circles);
  return globalThis.d3.packEnclose(circles);
}

/** Service disc and footprint radii plus each service's ring plan. */
function serviceSizes(S, sLs, sLe, SVIN) {
  const RS = new Float32Array(S),
    RF = new Float32Array(S),
    plans = new Array(S);
  for (let s = 0; s < S; s++) {
    const n = sLe[s] - sLs[s];
    RS[s] = 5.5 + 1.6 * Math.sqrt(Math.min(n + 0.35 * SVIN[s], 420));
    plans[s] = ringPlan(n, RS[s]);
    RF[s] = (plans[s].ds.length ? plans[s].ds[plans[s].ds.length - 1] : RS[s]) + 5;
  }
  return { RS, RF, plans };
}

/** Nested circle packing: services in domains, domains in repos, repos in the world. */
function packHierarchy(P, idx, RF) {
  const { S, D, R, dSs, dSe, rDs, rDe, domRepo, hub } = P,
    { sp, dp, rp } = idx;
  const sx = new Float64Array(S),
    sy = new Float64Array(S),
    dR = new Float64Array(D),
    dlx = new Float64Array(D),
    dly = new Float64Array(D);
  const rR = new Float64Array(R),
    rx = new Float64Array(R),
    ry = new Float64Array(R);
  for (let d = 0; d < D; d++) {
    const list = [];
    for (let s = dSs[d]; s < dSe[d]; s++) list.push(s);
    const ord =
      list.length > 70
        ? list.sort((a, b) => hub[b] - hub[a])
        : affinityOrder(
            list,
            (a, b) => pairWeight(sp, S, a, b),
            s => hub[s],
          );
    const cs = ord.map(s => ({ r: RF[s] + PAD.service, s })),
      enc = pack(cs);
    for (const c of cs) {
      sx[c.s] = c.x - enc.x;
      sy[c.s] = c.y - enc.y;
    }
    dR[d] = enc.r + PAD.domain;
  }
  for (let r = 0; r < R; r++) {
    const list = [];
    for (let d = rDs[r]; d < rDe[r]; d++) list.push(d);
    const cs = affinityOrder(
        list,
        (a, b) => pairWeight(dp, D, a, b),
        d => dR[d],
      ).map(d => ({ r: dR[d], d })),
      enc = pack(cs);
    for (const c of cs) {
      dlx[c.d] = c.x - enc.x;
      dly[c.d] = c.y - enc.y;
    }
    rR[r] = enc.r + PAD.repo;
  }
  {
    const cs = affinityOrder(
        Array.from({ length: R }, (_, r) => r),
        (a, b) => pairWeight(rp, R, a, b),
        r => rR[r],
      ).map(r => ({ r: rR[r] + PAD.world, id: r })),
      enc = pack(cs);
    for (const c of cs) {
      rx[c.id] = c.x - enc.x;
      ry[c.id] = c.y - enc.y;
    }
  }
  const dcx = new Float32Array(D),
    dcy = new Float32Array(D);
  for (let d = 0; d < D; d++) {
    const r = domRepo[d];
    dcx[d] = rx[r] + dlx[d];
    dcy[d] = ry[r] + dly[d];
  }
  return { sx, sy, dR, rR, rx, ry, dcx, dcy };
}

/** Put each endpoint on its service's rings, on the side facing the services it talks to (fewer crossings). */
function placeEndpoints(P, idx, plans, PX, PY, PR) {
  const { S, sLs, sLe, KND, CS, CD, own } = P,
    { AO, AE } = idx;
  for (let s = 0; s < S; s++) {
    const { ds, take } = plans[s],
      slots = [];
    take.forEach((tk, ri) => {
      const off = ri % 2 ? Math.PI / Math.max(tk, 1) : 0;
      for (let j = 0; j < tk; j++)
        slots.push({ ring: ri, d: ds[ri], a: off + (j * 2 * Math.PI) / tk - Math.PI, used: false });
    });
    const pref = [],
      rest = [];
    for (let i = sLs[s]; i < sLe[s]; i++) {
      let vx = 0,
        vy = 0;
      for (let j = AO[i]; j < AO[i + 1]; j++) {
        const e = AE[j],
          o = CS[e] === i ? CD[e] : CS[e],
          os = own(o);
        if (os === s) continue;
        const dx = PX[os] - PX[s],
          dy = PY[os] - PY[s],
          l = Math.hypot(dx, dy) || 1;
        vx += dx / l;
        vy += dy / l;
      }
      const m = Math.hypot(vx, vy);
      if (m > 0.01) pref.push({ i, a: Math.atan2(vy, vx), m });
      else rest.push(i);
    }
    const put = (i, t) => {
      PX[i] = PX[s] + Math.cos(t.a) * t.d;
      PY[i] = PY[s] + Math.sin(t.a) * t.d;
    };
    pref.sort((p, q) => q.m - p.m);
    for (const p of pref) {
      let best = -1,
        bc = 1e9;
      for (let j = 0; j < slots.length; j++) {
        if (slots[j].used) continue;
        const c = angDiff(slots[j].a, p.a) - 0.3 * slots[j].ring;
        if (c < bc) {
          bc = c;
          best = j;
        }
      }
      slots[best].used = true;
      put(p.i, slots[best]);
    }
    rest.sort((a, b) => KND[a] - KND[b]);
    const free = slots.filter(x => !x.used).sort((a, b) => a.a - b.a);
    rest.forEach((i, j) => put(i, free[j]));
    for (let i = sLs[s]; i < sLe[s]; i++) PR[i] = LEAF_RADIUS[KND[i]];
  }
}

/** Territory outlines: convex hulls of padded service footprints, per domain and per repository. */
function territories(P, RF, PX, PY) {
  const { D, R, dSs, dSe, rDs, rDe } = P;
  const ring = (arr, s, r, n) => {
    for (let j = 0; j < n; j++) {
      const a = (j / n) * 2 * Math.PI;
      arr.push([PX[s] + Math.cos(a) * r, PY[s] + Math.sin(a) * r]);
    }
  };
  const dHull = new Array(D),
    rHull = new Array(R);
  for (let d = 0; d < D; d++) {
    const pts = [];
    for (let s = dSs[d]; s < dSe[d]; s++) ring(pts, s, RF[s] + PAD.domainHull, 10);
    dHull[d] = convexHull(pts);
  }
  for (let r = 0; r < R; r++) {
    const pts = [];
    for (let d = rDs[r]; d < rDe[r]; d++) for (let s = dSs[d]; s < dSe[d]; s++) ring(pts, s, RF[s] + PAD.repoHull, 8);
    rHull[r] = convexHull(pts);
  }
  return { dHull, rHull, dTop: Float32Array.from(dHull.map(hullTop)), rTop: Float32Array.from(rHull.map(hullTop)) };
}

/** Static uniform grid (CSR) over all nodes, for O(1) picking and viewport queries. */
function spatialGrid(N, PX, PY, bounds) {
  const { x0, y0, x1, y1 } = bounds,
    CELL = GRID_CELL,
    GC = Math.ceil((x1 - x0) / CELL) + 1,
    GR = Math.ceil((y1 - y0) / CELL) + 1;
  const cellOf = i =>
    clamp(Math.floor((PY[i] - y0) / CELL), 0, GR - 1) * GC + clamp(Math.floor((PX[i] - x0) / CELL), 0, GC - 1);
  const GO = new Uint32Array(GC * GR + 1);
  for (let i = 0; i < N; i++) GO[cellOf(i) + 1]++;
  for (let c = 0; c < GC * GR; c++) GO[c + 1] += GO[c];
  const GI = new Uint32Array(N),
    fill = GO.slice(0, GC * GR);
  for (let i = 0; i < N; i++) GI[fill[cellOf(i)]++] = i;
  return { x0, y0, CELL, GC, GR, GO, GI };
}

function worldBounds(R, rx, ry, rR) {
  let x0 = 1e9,
    y0 = 1e9,
    x1 = -1e9,
    y1 = -1e9;
  for (let r = 0; r < R; r++) {
    x0 = Math.min(x0, rx[r] - rR[r]);
    x1 = Math.max(x1, rx[r] + rR[r]);
    y0 = Math.min(y0, ry[r] - rR[r]);
    y1 = Math.max(y1, ry[r] + rR[r]);
  }
  return { x0, y0, x1, y1 };
}

/** The graph object returned by finish(); fields are described in docs/ARCHITECTURE.md. */
function assembleGraph(P, { own, name, idx, RS, RF, PX, PY, PR, H, T, bounds, grid, T0, T1, T2 }) {
  const {
    N,
    S,
    L,
    R,
    D,
    KND,
    leafSvc,
    sLs,
    sLe,
    svcDom,
    dSs,
    dSe,
    domRepo,
    rDs,
    rDe,
    repoName,
    domName,
    svcName,
    CS,
    CD,
    CST,
  } = P;
  const { AO, AE, ISS, SVST, REL, BYST, sp, dp, rp, dr, RO, RI } = idx;
  const g = {
    N,
    S,
    L,
    R,
    D,
    C: CS.length,
    KND,
    leafSvc,
    sLs,
    sLe,
    svcDom,
    dSs,
    dSe,
    domRepo,
    rDs,
    rDe,
    repoName,
    domName,
    svcName,
    name,
    own,
    CS,
    CD,
    CST,
    AO,
    AE,
    ISS,
    SVST,
    REL,
    BYST,
    sp,
    dp,
    rp,
    dr,
    RO,
    RI,
    RS,
    RF,
    PX,
    PY,
    PR,
    dcx: H.dcx,
    dcy: H.dcy,
    dR: H.dR,
    rx: Float32Array.from(H.rx),
    ry: Float32Array.from(H.ry),
    rR: H.rR,
    ...T,
    grid,
    bounds,
    medD: median(H.dR),
    medRF: median(RF),
    medRS: median(RS),
    maxRS: Math.max(...RS),
    svcOrder: byDesc(S, RF),
    domOrder: byDesc(D, H.dR),
    repoOrder: byDesc(R, H.rR),
    tGen: T1 - T0,
    tLay: T2 - T1,
  };
  g.bytes =
    Object.values(g).reduce((a, v) => a + (ArrayBuffer.isView(v) ? v.byteLength : 0), 0) +
    [sp, dp, rp, dr].reduce((a, t) => a + t.a.byteLength + t.b.byteLength + t.c.byteLength, 0) +
    svcName.reduce((a, s) => a + s.length * 2, 0);
  return g;
}

const byDesc = (n, key) => Uint32Array.from(Array.from({ length: n }, (_, i) => i).sort((a, b) => key[b] - key[a]));

/**
 * Index and lay out a raw graph. See docs/GRAPH_SPEC.md for the input shape and docs/ARCHITECTURE.md for the output.
 * @param {object} P raw graph: sizes N,S,L,R,D; hierarchy ranges; KND, leafSvc; names; hub; contracts CS,CD,CST; T0
 */
export function finish(P) {
  const { N, S, R, leafSvc, sLs, sLe, svcDom, svcName, leafName, CS, CD, T0 } = P;
  const own = i => (i < S ? i : leafSvc[i - S]);
  const name = i => (i < S ? svcName[i] : leafName(i));
  const g0 = { ...P, own };
  const idx = { ...adjacency(N, CS, CD), ...statusStats(g0) };
  Object.assign(idx, aggregates(g0));
  Object.assign(idx, forwardIndex(S, idx.dr));
  const T1 = performance.now();

  const { RS, RF, plans } = serviceSizes(S, sLs, sLe, idx.SVIN);
  const H = packHierarchy(P, idx, RF);
  const PX = new Float32Array(N),
    PY = new Float32Array(N),
    PR = new Float32Array(N);
  for (let s = 0; s < S; s++) {
    const d = svcDom[s];
    PX[s] = H.dcx[d] + H.sx[s];
    PY[s] = H.dcy[d] + H.sy[s];
    PR[s] = RS[s];
  }
  placeEndpoints(g0, idx, plans, PX, PY, PR);
  const T = territories(P, RF, PX, PY);
  const bounds = worldBounds(R, H.rx, H.ry, H.rR);
  const grid = spatialGrid(N, PX, PY, bounds);
  const T2 = performance.now();

  return assembleGraph(P, { own, name, idx, RS, RF, PX, PY, PR, H, T, bounds, grid, T0, T1, T2 });
}
