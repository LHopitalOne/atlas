/**
 * Deterministic synthetic graph generator (same size => same graph, so links stay stable).
 * Produces the raw hierarchy and contracts; model/layout.js `finish` turns them into a laid-out graph.
 *
 * Stages run in a fixed order because they share one seeded random stream:
 *   sizes -> counts -> hierarchy -> names -> contracts
 */
import { finish } from './layout.js';
import { syntheticDoc } from './describe.js';
import { DOMW, EVT, hash32, METHODS, MOD, mulberry32, NOUNS, REPO_A, REPO_B, SFX, SUF } from './vocab.js';

/** Contract status odds by scope (same domain, same repo, cross-repo): cumulative thresholds for [matched, ambiguous]; the rest is unmatched. */
const STATUS_ODDS = [
  [0.82, 0.92],
  [0.72, 0.86],
  [0.5, 0.76],
];
/** Chance a link is a service-level inference instead of an endpoint contract, by scope. */
const INFERRED_ODDS = [0.07, 0.07, 0.15];
/** Endpoint kinds: cumulative odds for [endpoint, event]; the rest are modules. */
const KIND_ODDS = [0.62, 0.76];
const MAX_LEAVES = 44,
  REFILL_BELOW = 24;
const FIRST_REPOS = ['AIProducts', 'MCPHub', 'SupportChatBot'];
const DOMAIN_SUFFIXES = ['core', 'edge', 'next', 'labs', 'legacy', 'ops'];

/** Seeded random helpers. */
function makeRandom(seed) {
  const rnd = mulberry32(seed);
  return {
    rnd,
    pick: a => a[(rnd() * a.length) | 0],
    gauss: () => {
      let u = 0;
      while (!u) u = rnd();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rnd());
    },
  };
}

/**
 * Split `total` across buckets in proportion to `w`, each bucket getting at least `min` (largest-remainder rounding).
 * @returns {Uint32Array}
 */
export function distribute(total, w, min) {
  const n = w.length,
    out = new Uint32Array(n).fill(min),
    rest = total - min * n,
    sw = w.reduce((a, b) => a + b, 0);
  let used = 0;
  const fr = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const v = (w[i] * rest) / sw,
      f = Math.floor(v);
    out[i] += f;
    used += f;
    fr[i] = v - f;
  }
  const ord = Array.from({ length: n }, (_, i) => i).sort((a, b) => fr[b] - fr[a]);
  for (let j = 0; j < rest - used; j++) out[ord[j % n]]++;
  return out;
}

const prefixSum = a => {
  const c = new Float64Array(a.length);
  let t = 0;
  for (let i = 0; i < a.length; i++) {
    t += a[i];
    c[i] = t;
  }
  return c;
};

/** Weighted pick of an index in [lo, hi) from a prefix-sum table. */
function sampleRange(rnd, c, lo, hi) {
  const base = lo > 0 ? c[lo - 1] : 0,
    x = base + rnd() * (c[hi - 1] - base);
  let a = lo,
    b = hi;
  while (a < b) {
    const m = (a + b) >> 1;
    if (c[m] > x) b = m;
    else a = m + 1;
  }
  return Math.min(a, hi - 1);
}

/** How many services, endpoints, repositories and domains a graph of N nodes gets. */
export function sizesFor(N) {
  const S = Math.max(12, Math.round(N / 6.25)),
    L = N - S,
    R = Math.max(3, Math.round(N / 1100)),
    D = Math.max(R * 2, Math.round(S / 7));
  return { N, S, L, R, D };
}

/** Heavy-tailed sizes: domains per repo, services per domain, endpoints per service. */
function makeCounts({ rnd, gauss }, { S, L, R, D }) {
  const repoW = [];
  for (let r = 0; r < R; r++) repoW.push((Math.exp(0.45 * gauss()) / Math.pow(r + 1, 0.3)) * (r === 0 ? 1.8 : 1));
  const domPerRepo = distribute(D, repoW, 2);
  const domW = [];
  for (let d = 0; d < D; d++) domW.push(Math.exp(0.55 * gauss()));
  const svcPerDom = distribute(S, domW, 2);
  const svcW = [];
  for (let s = 0; s < S; s++) svcW.push(Math.exp(0.8 * gauss()));
  const leafPerSvc = distribute(L, svcW, 2);
  let over = 0;
  for (let s = 0; s < S; s++)
    if (leafPerSvc[s] > MAX_LEAVES) {
      over += leafPerSvc[s] - MAX_LEAVES;
      leafPerSvc[s] = MAX_LEAVES;
    }
  while (over > 0) {
    const j = (rnd() * S) | 0;
    if (leafPerSvc[j] < REFILL_BELOW) {
      leafPerSvc[j]++;
      over--;
    }
  }
  return { domPerRepo, svcPerDom, leafPerSvc };
}

/** Contiguous ranges: repo -> domains [rDs, rDe), domain -> services [dSs, dSe), service -> endpoints [sLs, sLe). */
function makeHierarchy({ rnd }, { N, S, L, R, D }, { domPerRepo, svcPerDom, leafPerSvc }) {
  const domRepo = new Uint16Array(D),
    rDs = new Uint32Array(R),
    rDe = new Uint32Array(R);
  {
    let d = 0;
    for (let r = 0; r < R; r++) {
      rDs[r] = d;
      for (let j = 0; j < domPerRepo[r]; j++) domRepo[d++] = r;
      rDe[r] = d;
    }
  }
  const svcDom = new Uint32Array(S),
    dSs = new Uint32Array(D),
    dSe = new Uint32Array(D);
  {
    let s = 0;
    for (let d = 0; d < D; d++) {
      dSs[d] = s;
      for (let j = 0; j < svcPerDom[d]; j++) svcDom[s++] = d;
      dSe[d] = s;
    }
  }
  const KND = new Uint8Array(N),
    leafSvc = new Uint32Array(L),
    sLs = new Uint32Array(S),
    sLe = new Uint32Array(S);
  let i = S;
  for (let s = 0; s < S; s++) {
    sLs[s] = i;
    for (let j = 0; j < leafPerSvc[s]; j++) {
      const x = rnd();
      KND[i] = x < KIND_ODDS[0] ? 1 : x < KIND_ODDS[1] ? 2 : 3;
      leafSvc[i - S] = s;
      i++;
    }
    sLe[s] = i;
  }
  return { domRepo, rDs, rDe, svcDom, dSs, dSe, KND, leafSvc, sLs, sLe };
}

/** Readable, mostly unique names for repositories, domains and services. */
function makeNames({ rnd, pick }, { S, R, D }, { rDs, rDe, dSs, dSe }) {
  const repoName = [],
    used = new Set(FIRST_REPOS);
  for (let r = 0; r < R; r++) {
    if (r < FIRST_REPOS.length) {
      repoName.push(FIRST_REPOS[r]);
      continue;
    }
    let nm,
      t = 0;
    do {
      nm = pick(REPO_A) + pick(REPO_B);
    } while (used.has(nm) && ++t < 300);
    if (used.has(nm)) nm += r;
    used.add(nm);
    repoName.push(nm);
  }
  const domName = new Array(D);
  for (let r = 0; r < R; r++) {
    const w = DOMW.slice(1);
    for (let i = w.length - 1; i > 0; i--) {
      const j = (rnd() * (i + 1)) | 0;
      [w[i], w[j]] = [w[j], w[i]];
    }
    if (r === 0) w.unshift('Platform');
    for (let j = 0; j < rDe[r] - rDs[r]; j++)
      domName[rDs[r] + j] =
        w[j % w.length] +
        (j >= w.length ? ' ' + DOMAIN_SUFFIXES[(((j / w.length) | 0) - 1) % DOMAIN_SUFFIXES.length] : '');
  }
  const svcName = new Array(S);
  for (let d = 0; d < D; d++) {
    const base = domName[d].toLowerCase().replace(/[^a-z0-9]+/g, '_'),
      u = new Set();
    for (let s = dSs[d]; s < dSe[d]; s++) {
      let nm,
        t = 0;
      do {
        nm = base + '_' + pick(SUF);
      } while (u.has(nm) && ++t < 40);
      if (u.has(nm)) nm += '_' + (s - dSs[d] + 1);
      u.add(nm);
      svcName[s] = nm;
    }
  }
  return { repoName, domName, svcName };
}

/** Endpoint names are derived from a hash on demand instead of stored (saves memory at 100k). */
function makeLeafName(seed, KND) {
  return i => {
    let h = hash32(((i + 1) * 0x9e3779b1) ^ seed);
    const res = NOUNS[h % NOUNS.length];
    h = hash32(h + 0x6d2b79f5);
    if (KND[i] === 1) return `${METHODS[h % METHODS.length]} /${res}${SFX[(h >>> 8) % SFX.length]}`;
    if (KND[i] === 2) return `${res}.${EVT[h % EVT.length]}`;
    return `${MOD[h % MOD.length]}/${res}.ts`;
  };
}

/** Contracts: mostly within a domain, some within the repository, some into the shared platform repo, a few anywhere. */
function makeContracts({ rnd, gauss }, { N, S, L, R, D }, h, { leafPerSvc }) {
  const { domRepo, rDs, rDe, svcDom, dSs, dSe, KND, sLs, sLe } = h;
  const hub = new Float64Array(S);
  for (let s = 0; s < S; s++)
    hub[s] = Math.pow(leafPerSvc[s], 0.8) * Math.exp(0.6 * gauss()) * (domRepo[svcDom[s]] === 0 ? 1.7 : 1);
  const cumH = prefixSum(hub),
    domHub = new Float64Array(D),
    repoHub = new Float64Array(R);
  for (let s = 0; s < S; s++) domHub[svcDom[s]] += hub[s];
  for (let d = 0; d < D; d++) repoHub[domRepo[d]] += domHub[d];
  const cumD = prefixSum(domHub),
    cumR = prefixSum(repoHub),
    cumSrc = prefixSum(Array.from(leafPerSvc));
  const pickLeaf = (s, caller) => {
    const lo = sLs[s],
      hi = sLe[s];
    let i = lo;
    for (let t = 0; t < 4; t++) {
      i = lo + ((rnd() * (hi - lo)) | 0);
      const k = KND[i];
      if (caller ? k === 3 : k !== 3) return i;
    }
    return i;
  };
  const pickTarget = (d, r, x) => {
    if (x < 0.5 && dSe[d] - dSs[d] > 1) return sampleRange(rnd, cumH, dSs[d], dSe[d]);
    if (x < 0.8 && rDe[r] - rDs[r] > 1) {
      const d2 = sampleRange(rnd, cumD, rDs[r], rDe[r]);
      return sampleRange(rnd, cumH, dSs[d2], dSe[d2]);
    }
    const r2 = x < 0.9 ? 0 : sampleRange(rnd, cumR, 0, R);
    const d2 = sampleRange(rnd, cumD, rDs[r2], rDe[r2]);
    return sampleRange(rnd, cumH, dSs[d2], dSe[d2]);
  };
  const CT = Math.round(N * 1.62) - L;
  let CS = new Uint32Array(CT),
    CD = new Uint32Array(CT),
    CST = new Uint8Array(CT);
  const seen = new Set();
  let ne = 0,
    guard = 0;
  while (ne < CT && guard++ < CT * 30) {
    const s = sampleRange(rnd, cumSrc, 0, S),
      d = svcDom[s],
      r = domRepo[d];
    const t = pickTarget(d, r, rnd());
    if (t === s) continue;
    const scope = svcDom[t] === d ? 0 : domRepo[svcDom[t]] === r ? 1 : 2;
    let a, b, st;
    if (rnd() < INFERRED_ODDS[scope]) {
      a = s;
      b = t;
      st = 3;
    } else {
      a = pickLeaf(s, true);
      b = pickLeaf(t, false);
      const y = rnd(),
        o = STATUS_ODDS[scope];
      st = y < o[0] ? 0 : y < o[1] ? 1 : 2;
    }
    const key = a * N + b;
    if (seen.has(key)) continue;
    seen.add(key);
    CS[ne] = a;
    CD[ne] = b;
    CST[ne] = st;
    ne++;
  }
  if (ne < CT) {
    CS = CS.slice(0, ne);
    CD = CD.slice(0, ne);
    CST = CST.slice(0, ne);
  }
  return { hub, CS, CD, CST };
}

/**
 * Generate and lay out a synthetic service graph of about N nodes.
 * @param {number} N node count (281, 5000, 25000, 100000 in the UI)
 */
export function build(N) {
  const T0 = performance.now();
  const random = makeRandom(0xa71a5 ^ N);
  const sizes = sizesFor(N);
  const counts = makeCounts(random, sizes);
  const hier = makeHierarchy(random, sizes, counts);
  const names = makeNames(random, sizes, hier);
  const leafName = makeLeafName(N, hier.KND);
  const contracts = makeContracts(random, sizes, hier, counts);
  const g = finish({ ...sizes, ...hier, ...names, leafName, ...contracts, T0 });
  // demo graphs have no source: summaries are simulated, signatures exist only for endpoints
  g.meta = { docSource: 'simulated' };
  g.doc = i => syntheticDoc(g, i);
  g.sig = i => (i < g.S ? '' : g.name(i));
  g.loc = () => '';
  g.end = () => 0;
  return g;
}
