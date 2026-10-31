/**
 * Route search over the directed service graph. Pure: no DOM, no global state.
 * The graph `g` is the object produced by model/layout.js (`finish`); it uses its directed pair table `g.dr`
 * ({a, b, c, n}: caller, callee, per-status counts, pair count) and the forward CSR index `g.RO`/`g.RI`.
 */

/**
 * Build (once) the reverse CSR index g.QO/g.QI: for each service, the pairs in which it is the callee.
 * @param {object} g graph from finish()
 */
export function ensureReverse(g) {
  if (g.QO) return;
  const S = g.S,
    QO = new Uint32Array(S + 1);
  for (let p = 0; p < g.dr.n; p++) QO[g.dr.b[p] + 1]++;
  for (let s = 0; s < S; s++) QO[s + 1] += QO[s];
  const QI = new Uint32Array(g.dr.n),
    fill = QO.slice(0, S);
  for (let p = 0; p < g.dr.n; p++) QI[fill[g.dr.b[p]]++] = p;
  g.QO = QO;
  g.QI = QI;
}

/** Number of distinct services that call service `s`. */
export function callerCount(g, s) {
  ensureReverse(g);
  return g.QO[s + 1] - g.QO[s];
}

/**
 * Multi-source breadth-first search: the shortest chain from any service in `src` to any service in `tgt`.
 * @param {object} g graph from finish()
 * @param {number[]} src start services
 * @param {number[]} tgt destination services
 * @param {{either?: boolean, avoid?: boolean}} [opts] either: also walk calls backwards; avoid: skip links whose only contracts are unmatched
 * @returns {{path: number[], via: Int32Array, fwd: Uint8Array} | null} path of service ids; via[v] = pair index used to reach v; fwd[v] = 1 if that step follows the call
 */
export function routeSearch(g, src, tgt, { either = false, avoid = false } = {}) {
  ensureReverse(g);
  const S = g.S,
    prev = new Int32Array(S).fill(-1),
    via = new Int32Array(S).fill(-1),
    fwd = new Uint8Array(S),
    isT = new Uint8Array(S);
  for (const t of tgt) isT[t] = 1;
  const q = new Uint32Array(S);
  let qh = 0,
    qt = 0,
    hit = -1;
  for (const s of src)
    if (prev[s] < 0) {
      prev[s] = s;
      q[qt++] = s;
    }
  const usable = p => !(avoid && g.dr.c[p * 4] + g.dr.c[p * 4 + 1] + g.dr.c[p * 4 + 3] === 0);
  while (qh < qt) {
    const u = q[qh++];
    if (isT[u]) {
      hit = u;
      break;
    }
    for (let j = g.RO[u]; j < g.RO[u + 1]; j++) {
      const p = g.RI[j],
        v = g.dr.b[p];
      if (prev[v] >= 0 || !usable(p)) continue;
      prev[v] = u;
      via[v] = p;
      fwd[v] = 1;
      q[qt++] = v;
    }
    if (either)
      for (let j = g.QO[u]; j < g.QO[u + 1]; j++) {
        const p = g.QI[j],
          v = g.dr.a[p];
        if (prev[v] >= 0 || !usable(p)) continue;
        prev[v] = u;
        via[v] = p;
        fwd[v] = 0;
        q[qt++] = v;
      }
  }
  if (hit < 0) return null;
  const path = [];
  let v = hit;
  while (prev[v] !== v) {
    path.push(v);
    v = prev[v];
  }
  path.push(v);
  path.reverse();
  return { path, via, fwd };
}
