/**
 * Indexes over the raw graph, computed once per dataset. Pure: arrays in, arrays out.
 *
 * Node ids: services are 0..S-1, endpoints ("leaves") are S..N-1. Contract e runs CS[e] -> CD[e] with status CST[e]
 * (0 resolved/matched, 1 ambiguous, 2 unresolved/unmatched, 3 inferred).
 */

/** CSR adjacency: contracts touching node i are AE[AO[i] .. AO[i+1]). */
export function adjacency(N, CS, CD) {
  const C = CS.length,
    AO = new Uint32Array(N + 1);
  for (let e = 0; e < C; e++) {
    AO[CS[e] + 1]++;
    AO[CD[e] + 1]++;
  }
  for (let i = 0; i < N; i++) AO[i + 1] += AO[i];
  const AE = new Uint32Array(AO[N]),
    fill = AO.slice(0, N);
  for (let e = 0; e < C; e++) {
    AE[fill[CS[e]]++] = e;
    AE[fill[CD[e]]++] = e;
  }
  return { AO, AE };
}

/**
 * Per-node and per-service status statistics.
 * ISS[i]: worst issue on node i (0 none, 1 ambiguous, 2 unmatched); SVST[s*4+st]: contracts of each status touching service s;
 * SVIN[s]: incoming contracts; BYST[st]: totals; REL[i]: 1 if the node is relevant in issues-only mode.
 */
export function statusStats({ N, S, CS, CD, CST, own }) {
  const ISS = new Uint8Array(N),
    SVST = new Uint32Array(S * 4),
    SVIN = new Uint32Array(S),
    BYST = [0, 0, 0, 0];
  for (let e = 0; e < CS.length; e++) {
    const st = CST[e],
      a = CS[e],
      b = CD[e];
    BYST[st]++;
    if (st === 1 || st === 2) {
      if (st > ISS[a]) ISS[a] = st;
      if (st > ISS[b]) ISS[b] = st;
    }
    const oa = own(a),
      ob = own(b);
    SVST[oa * 4 + st]++;
    SVST[ob * 4 + st]++;
    SVIN[ob]++;
  }
  const REL = new Uint8Array(N);
  for (let i = 0; i < N; i++) REL[i] = i < S ? SVST[i * 4 + 1] + SVST[i * 4 + 2] > 0 : ISS[i] > 0;
  return { ISS, SVST, SVIN, BYST, REL };
}

/**
 * Contracts aggregated between services, domains and repositories (undirected: sp, dp, rp), plus a directed
 * service table (dr) for routing that also remembers one representative contract per status.
 * Each table: { a, b, c (4 status counts per pair), n, map ((min*mult+max) -> pair) [, rep] }.
 */
export function aggregates({ S, D, R, CS, CD, CST, own, svcDom, domRepo }) {
  const mk = () => ({ map: new Map(), a: [], b: [], c: [] });
  const SP = mk(),
    DP = mk(),
    RP = mk(),
    DR = mk();
  DR.rep = [];
  const addUndirected = (g, x, y, mult, st) => {
    if (x > y) {
      const t = x;
      x = y;
      y = t;
    }
    const k = x * mult + y;
    let p = g.map.get(k);
    if (p === undefined) {
      p = g.a.length;
      g.map.set(k, p);
      g.a.push(x);
      g.b.push(y);
      g.c.push(0, 0, 0, 0);
    }
    g.c[p * 4 + st]++;
  };
  const addDirected = (a, b, st, e) => {
    const k = a * S + b;
    let p = DR.map.get(k);
    if (p === undefined) {
      p = DR.a.length;
      DR.map.set(k, p);
      DR.a.push(a);
      DR.b.push(b);
      DR.c.push(0, 0, 0, 0);
      DR.rep.push(-1, -1, -1, -1);
    }
    DR.c[p * 4 + st]++;
    if (DR.rep[p * 4 + st] < 0) DR.rep[p * 4 + st] = e;
  };
  for (let e = 0; e < CS.length; e++) {
    const a = own(CS[e]),
      b = own(CD[e]),
      st = CST[e];
    if (a === b) continue;
    addUndirected(SP, a, b, S, st);
    addDirected(a, b, st, e);
    const da = svcDom[a],
      db = svcDom[b];
    if (da !== db) addUndirected(DP, da, db, D, st);
    const ra = domRepo[da],
      rb = domRepo[db];
    if (ra !== rb) addUndirected(RP, ra, rb, R, st);
  }
  const seal = g => ({
    map: g.map,
    a: Uint32Array.from(g.a),
    b: Uint32Array.from(g.b),
    c: Uint32Array.from(g.c),
    rep: g.rep ? Int32Array.from(g.rep) : null,
    n: g.a.length,
  });
  return { sp: seal(SP), dp: seal(DP), rp: seal(RP), dr: seal(DR) };
}

/** Forward CSR over the directed table: pairs where service s is the caller are RI[RO[s] .. RO[s+1]). */
export function forwardIndex(S, dr) {
  const RO = new Uint32Array(S + 1);
  for (let p = 0; p < dr.n; p++) RO[dr.a[p] + 1]++;
  for (let s = 0; s < S; s++) RO[s + 1] += RO[s];
  const RI = new Uint32Array(dr.n),
    fill = RO.slice(0, S);
  for (let p = 0; p < dr.n; p++) RI[fill[dr.a[p]]++] = p;
  return { RO, RI };
}

/** Total contracts in a pair table between x and y (order-insensitive). */
export function pairWeight(g, mult, x, y) {
  if (x > y) {
    const t = x;
    x = y;
    y = t;
  }
  const p = g.map.get(x * mult + y);
  return p === undefined ? 0 : g.c[p * 4] + g.c[p * 4 + 1] + g.c[p * 4 + 2] + g.c[p * 4 + 3];
}
