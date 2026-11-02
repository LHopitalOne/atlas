/**
 * Dependency cycles: groups of services (or domains) that depend on each other in a loop, so none of them can change
 * or be tested alone. Pure. Uses the directed service table `g.dr` (caller -> callee) and its forward index `g.RO/RI`.
 */

/**
 * Strongly connected components of a directed graph given as an adjacency callback (iterative Tarjan, no recursion).
 * @param {number} n node count
 * @param {(u:number, visit:(v:number)=>void)=>void} each calls visit(v) for every edge u -> v
 * @returns {number[][]} components with more than one node, largest first
 */
export function loops(n, each) {
  const index = new Int32Array(n).fill(-1),
    low = new Int32Array(n),
    onStack = new Uint8Array(n);
  const stack = [],
    out = [];
  let next = 0;
  const succ = u => {
    const a = [];
    each(u, v => a.push(v));
    return a;
  };
  for (let root = 0; root < n; root++) {
    if (index[root] >= 0) continue;
    const work = [[root, succ(root), 0]];
    index[root] = low[root] = next++;
    stack.push(root);
    onStack[root] = 1;
    while (work.length) {
      const top = work[work.length - 1],
        [u, vs] = top;
      if (top[2] < vs.length) {
        const v = vs[top[2]++];
        if (index[v] < 0) {
          index[v] = low[v] = next++;
          stack.push(v);
          onStack[v] = 1;
          work.push([v, succ(v), 0]);
        } else if (onStack[v]) low[u] = Math.min(low[u], index[v]);
        continue;
      }
      work.pop();
      if (work.length) {
        const p = work[work.length - 1][0];
        low[p] = Math.min(low[p], low[u]);
      }
      if (low[u] === index[u]) {
        const comp = [];
        let w;
        do {
          w = stack.pop();
          onStack[w] = 0;
          comp.push(w);
        } while (w !== u);
        if (comp.length > 1) out.push(comp);
      }
    }
  }
  return out.sort((a, b) => b.length - a.length);
}

/** Shortest loop from `start` back to itself, staying inside `members`. Returns [start, ..., start] or null. */
export function shortestLoop(start, members, each) {
  const inSet = new Set(members),
    prev = new Map([[start, -1]]),
    q = [start];
  for (let h = 0; h < q.length; h++) {
    const u = q[h];
    let found = false;
    each(u, v => {
      if (found || !inSet.has(v)) return;
      if (v === start) {
        found = true;
        prev.set('end', u);
        return;
      }
      if (!prev.has(v)) {
        prev.set(v, u);
        q.push(v);
      }
    });
    if (found) {
      const path = [start];
      for (let v = prev.get('end'); v !== start; v = prev.get(v)) path.push(v);
      path.push(start);
      return [start, ...path.slice(1, -1).reverse(), start];
    }
  }
  return null;
}

const serviceEdges = g => (u, visit) => {
  for (let j = g.RO[u]; j < g.RO[u + 1]; j++) visit(g.dr.b[g.RI[j]]);
};

/** Domain-level edges (a domain calls another when any of its services calls one there), built once per graph. */
function domainEdges(g) {
  if (!g._domAdj) {
    const adj = Array.from({ length: g.D }, () => new Set());
    for (let p = 0; p < g.dr.n; p++) {
      const a = g.svcDom[g.dr.a[p]],
        b = g.svcDom[g.dr.b[p]];
      if (a !== b) adj[a].add(b);
    }
    g._domAdj = adj.map(s => [...s]);
  }
  return (u, visit) => g._domAdj[u].forEach(visit);
}

/**
 * Cycles at one level, each with its shortest loop through its most-called member.
 * @param {'service'|'domain'} level
 * @returns {{groups:{members:number[], loop:number[]}[], inGroup:Int32Array}} inGroup[i] = group index or -1
 */
export function cyclesOf(g, level = 'service') {
  const key = `_cycles_${level}`;
  if (g[key]) return g[key];
  const n = level === 'service' ? g.S : g.D,
    each = level === 'service' ? serviceEdges(g) : domainEdges(g);
  const indeg = new Int32Array(n);
  for (let u = 0; u < n; u++) each(u, v => indeg[v]++);
  const comps = loops(n, each),
    inGroup = new Int32Array(n).fill(-1);
  const groups = comps.map((members, k) => {
    members.forEach(m => (inGroup[m] = k));
    const hub = members.reduce((a, b) => (indeg[b] > indeg[a] ? b : a));
    return { members, loop: shortestLoop(hub, members, each) };
  });
  return (g[key] = { groups, inGroup, each });
}

/** The shortest loop through one service (or domain), or null if it isn't in a cycle. */
export function loopThrough(g, id, level = 'service') {
  const c = cyclesOf(g, level),
    k = c.inGroup[id];
  return k < 0 ? null : { loop: shortestLoop(id, c.groups[k].members, c.each), size: c.groups[k].members.length };
}
