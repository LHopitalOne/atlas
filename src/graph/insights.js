/**
 * What a service means in the graph: its roles and how far a change to it reaches. Pure: no DOM, no global state.
 * Uses the directed service table `g.dr` and its forward (`RO/RI`) and reverse (`QO/QI`) indexes.
 */
import { ensureReverse } from './route-search.js';

const callers = (g, s) => g.QO[s + 1] - g.QO[s];
const callees = (g, s) => g.RO[s + 1] - g.RO[s];

/** Fewest callers that make a service a hub: the top 5% of services with callers, and at least 5. */
function hubThreshold(g) {
  if (g._hubMin === undefined) {
    const c = [];
    for (let s = 0; s < g.S; s++) if (callers(g, s) > 0) c.push(callers(g, s));
    c.sort((a, b) => a - b);
    g._hubMin = Math.max(5, c.length ? c[Math.floor(c.length * 0.95)] : 5);
  }
  return g._hubMin;
}

/** Repositories that call into other repositories. Ones that never do (libraries, platform APIs) can't be bridged to. */
function onwardRepos(g) {
  if (!g._onward) {
    g._onward = new Uint8Array(g.R);
    for (let p = 0; p < g.dr.n; p++) {
      const ra = g.domRepo[g.svcDom[g.dr.a[p]]],
        rb = g.domRepo[g.svcDom[g.dr.b[p]]];
      if (ra !== rb) g._onward[ra] = 1;
    }
  }
  return g._onward;
}

/**
 * Roles of service s, computed from the graph.
 * @returns {{key:'entry'|'hub'|'bridge'|'deadEnd'|'isolated', label:string, detail:string}[]}
 */
export function rolesOf(g, s) {
  ensureReverse(g);
  const nIn = callers(g, s),
    nOut = callees(g, s),
    out = [];
  if (!nIn && !nOut) return [{ key: 'isolated', label: 'Isolated', detail: 'No known calls in or out.' }];
  if (!nIn) out.push({ key: 'entry', label: 'Entry point', detail: 'Nothing calls it; work starts here.' });
  if (nIn >= hubThreshold(g))
    out.push({ key: 'hub', label: 'Hub', detail: `Used by ${nIn} services, more than 95% of the map.` });
  const home = g.domRepo[g.svcDom[s]],
    repo = t => g.domRepo[g.svcDom[t]];
  const from = new Set(),
    to = new Set();
  for (let j = g.QO[s]; j < g.QO[s + 1]; j++) {
    const r = repo(g.dr.a[g.QI[j]]);
    if (r !== home) from.add(r);
  }
  for (let j = g.RO[s]; j < g.RO[s + 1]; j++) {
    const r = repo(g.dr.b[g.RI[j]]);
    if (r !== home && onwardRepos(g)[r]) to.add(r);
  }
  if (from.size && to.size) {
    const names = set =>
      [...set]
        .slice(0, 2)
        .map(r => g.repoName[r])
        .join(' and ') + (set.size > 2 ? ` and ${set.size - 2} more` : '');
    out.push({ key: 'bridge', label: 'Bridge', detail: `Passes calls from ${names(from)} on to ${names(to)}.` });
  }
  if (!nOut) out.push({ key: 'deadEnd', label: 'Dead end', detail: 'Calls nothing else; changes stop here.' });
  return out;
}

/**
 * Everything that could break if service s changes: every service that calls it, directly or through others.
 * @returns {{services:number[], repos:number, direct:number, via:Int32Array}} services in breadth-first order
 *   (nearest first); via[t] = the pair index that reached t, for drawing the chain
 */
export function impactOf(g, s) {
  ensureReverse(g);
  const seen = new Uint8Array(g.S),
    via = new Int32Array(g.S).fill(-1),
    q = [s],
    services = [];
  seen[s] = 1;
  for (let h = 0; h < q.length; h++) {
    const u = q[h];
    for (let j = g.QO[u]; j < g.QO[u + 1]; j++) {
      const p = g.QI[j],
        v = g.dr.a[p];
      if (seen[v]) continue;
      seen[v] = 1;
      via[v] = p;
      q.push(v);
      services.push(v);
    }
  }
  const repos = new Set(services.map(t => g.domRepo[g.svcDom[t]]));
  return { services, repos: repos.size, direct: callers(g, s), via };
}

/** A contract that represents pair p (the first status that has one), for drawing. */
export function pairContract(g, p) {
  for (let k = 0; k < 4; k++) {
    const e = g.dr.rep[p * 4 + k];
    if (e >= 0) return e;
  }
  return -1;
}
