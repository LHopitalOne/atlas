/**
 * What Atlas can look up to answer a question: the same small set of tools for Claude (ask/claude.js), the offline
 * answerer (ask/local.js) and, in the product, AI agents. Pure: works on the graph object, returns plain data.
 *
 * References: `n<id>` for services and endpoints, `d<id>` for domains, `r<id>` for repositories.
 */
import { routeSearch } from '../graph/route-search.js';
import { impactOf, rolesOf } from '../graph/insights.js';

const LIMIT = 10;

/** Parse a reference or a name into { t: 'n'|'d'|'r', id }, or null. Names match exactly (case-insensitive), services first. */
export function resolve(g, ref) {
  const s = String(ref ?? '')
    .trim()
    .replace(/^@/, '');
  const m = s.match(/^([ndr])(\d+)$/);
  if (m) {
    const t = m[1],
      id = +m[2],
      max = t === 'n' ? g.N : t === 'd' ? g.D : g.R;
    return id < max ? { t, id } : null;
  }
  const low = s.toLowerCase();
  if (!low) return null;
  for (let i = 0; i < g.S; i++) if (g.svcName[i].toLowerCase() === low) return { t: 'n', id: i };
  for (let i = g.S; i < g.N; i++) if (g.name(i).toLowerCase() === low) return { t: 'n', id: i };
  for (let d = 0; d < g.D; d++) if (g.domName[d].toLowerCase() === low) return { t: 'd', id: d };
  for (let r = 0; r < g.R; r++) if (g.repoName[r].toLowerCase() === low) return { t: 'r', id: r };
  return null;
}

export const refOf = (t, id) => t + id;

/** Display name of a reference. */
export function refName(g, ref) {
  const e = resolve(g, ref);
  if (!e) return String(ref);
  return e.t === 'n' ? g.name(e.id) : e.t === 'd' ? g.domName[e.id] : g.repoName[e.id];
}

const where = (g, i) => {
  const s = g.own(i),
    d = g.svcDom[s];
  return `${g.repoName[g.domRepo[d]]} > ${g.domName[d]}${i < g.S ? '' : ` > ${g.svcName[s]}`}`;
};
const brief = (g, i) => ({ ref: refOf('n', i), name: g.name(i), where: where(g, i) });
const docOf = (g, i) => (g.doc ? g.doc(i) || '' : '');
const words = q =>
  String(q)
    .toLowerCase()
    .split(/[^a-z0-9_/.-]+/)
    .filter(w => w.length >= 3);

/** Find services, endpoints, domains and repositories by name or by what they do. */
export function search(g, { query, limit = 8 }) {
  const q = String(query || '')
      .toLowerCase()
      .trim(),
    ws = words(q),
    out = [];
  if (!q) return [];
  const score = (name, doc) => {
    const n = name.toLowerCase();
    if (n === q) return 1000;
    if (n.includes(q)) return 800 - n.length;
    if (ws.length && ws.every(w => n.includes(w))) return 600 - n.length;
    if (ws.length && doc && ws.every(w => doc.includes(w))) return 400 - doc.length / 10;
    if (ws.length && doc && ws.filter(w => doc.includes(w) || n.includes(w)).length >= Math.max(1, ws.length - 1))
      return 200;
    return -1;
  };
  for (let r = 0; r < g.R; r++) {
    const s = score(g.repoName[r], '');
    if (s > 0) out.push([s + 50, { ref: refOf('r', r), name: g.repoName[r], kind: 'repository' }]);
  }
  for (let d = 0; d < g.D; d++) {
    const s = score(g.domName[d], '');
    if (s > 0)
      out.push([s + 40, { ref: refOf('d', d), name: g.domName[d], kind: 'domain', where: g.repoName[g.domRepo[d]] }]);
  }
  for (let i = 0; i < g.N; i++) {
    const doc = docOf(g, i),
      s = score(g.name(i), doc.toLowerCase());
    if (s > 0)
      out.push([
        s + (i < g.S ? 30 : 0),
        { ...brief(g, i), kind: i < g.S ? 'service' : 'endpoint', summary: doc.slice(0, 160) },
      ]);
  }
  return out
    .sort((a, b) => b[0] - a[0])
    .slice(0, Math.min(Number(limit) || 8, 20))
    .map(x => x[1]);
}

/** Everything known about one service or endpoint. */
export function describe(g, { ref }) {
  const e = resolve(g, ref);
  if (!e) throw new Error(`No item called "${ref}". Search first.`);
  if (e.t !== 'n') return describeTerritory(g, e);
  const i = e.id,
    svc = i < g.S,
    out = { ...brief(g, i), kind: svc ? 'service' : 'endpoint' };
  const doc = docOf(g, i);
  out.summary = doc || null;
  out.summarySource = !doc
    ? 'none'
    : g.meta && g.meta.docSource === 'simulated'
      ? 'simulated (demo data)'
      : g.meta && g.meta.docSource === 'comment'
        ? 'doc comment in the code'
        : 'graph spec';
  if (g.sig && g.sig(i)) out.signature = g.sig(i);
  if (g.loc && typeof g.loc(i) === 'string' && g.loc(i))
    out.location = g.loc(i) + (g.end && g.end(i) ? `-${g.end(i)}` : '');
  if (svc) {
    out.roles = rolesOf(g, i).map(r => `${r.label}: ${r.detail}`);
    const usedBy = [],
      dependsOn = [];
    for (let j = g.QO[i]; j < g.QO[i + 1]; j++) usedBy.push(brief(g, g.dr.a[g.QI[j]]));
    for (let j = g.RO[i]; j < g.RO[i + 1]; j++) dependsOn.push(brief(g, g.dr.b[g.RI[j]]));
    Object.assign(out, {
      usedByCount: usedBy.length,
      usedBy: usedBy.slice(0, LIMIT),
      dependsOnCount: dependsOn.length,
      dependsOn: dependsOn.slice(0, LIMIT),
      endpoints: g.sLe[i] - g.sLs[i],
    });
  } else {
    const calledBy = [],
      calls = [];
    for (let j = g.AO[i]; j < g.AO[i + 1]; j++) {
      const c = g.AE[j];
      (g.CS[c] === i ? calls : calledBy).push(brief(g, g.CS[c] === i ? g.CD[c] : g.CS[c]));
    }
    Object.assign(out, { calledBy: calledBy.slice(0, LIMIT), calls: calls.slice(0, LIMIT) });
  }
  out.issues = g.ISS[i] === 2 ? 'has an unmatched contract' : g.ISS[i] === 1 ? 'has an ambiguous contract' : 'none';
  return out;
}

function describeTerritory(g, e) {
  if (e.t === 'd') {
    const d = e.id,
      svcs = [];
    for (let s = g.dSs[d]; s < g.dSe[d]; s++) svcs.push(brief(g, s));
    return {
      ref: refOf('d', d),
      name: g.domName[d],
      kind: 'domain',
      repository: g.repoName[g.domRepo[d]],
      services: svcs.length,
      examples: svcs.slice(0, LIMIT),
    };
  }
  const r = e.id,
    doms = [];
  for (let d = g.rDs[r]; d < g.rDe[r]; d++)
    doms.push({ ref: refOf('d', d), name: g.domName[d], services: g.dSe[d] - g.dSs[d] });
  return {
    ref: refOf('r', r),
    name: g.repoName[r],
    kind: 'repository',
    domains: doms.slice(0, 20),
    domainCount: doms.length,
  };
}

/** What could break if a service changes. Endpoints are measured through their service. */
export function impact(g, { ref }) {
  const e = resolve(g, ref);
  if (!e || e.t !== 'n') throw new Error(`Impact needs a service or endpoint, got "${ref}".`);
  const s = g.own(e.id),
    im = impactOf(g, s);
  return {
    ref: refOf('n', s),
    name: g.svcName[s],
    measuredThroughService: e.id !== s,
    affects: im.services.length,
    repositories: im.repos,
    directCallers: im.direct,
    nearest: im.services.slice(0, 12).map(t => brief(g, t)),
  };
}

/** How one thing reaches another, following calls (or, if no chain exists, either direction). */
export function route(g, { from, to }) {
  const a = resolve(g, from),
    b = resolve(g, to);
  if (!a || !b) throw new Error(`Couldn't find ${!a ? `"${from}"` : `"${to}"`}. Search first.`);
  const svcs = e => {
    if (e.t === 'n') return [g.own(e.id)];
    const out = [],
      [d0, d1] = e.t === 'd' ? [e.id, e.id + 1] : [g.rDs[e.id], g.rDe[e.id]];
    for (let d = d0; d < d1; d++) for (let s = g.dSs[d]; s < g.dSe[d]; s++) out.push(s);
    return out;
  };
  let r = routeSearch(g, svcs(a), svcs(b)),
    followsCalls = true;
  if (!r) {
    r = routeSearch(g, svcs(a), svcs(b), { either: true });
    followsCalls = false;
  }
  if (!r) return { found: false, from: refName(g, from), to: refName(g, to) };
  return {
    found: true,
    followsCalls,
    hops: r.path.length - 1,
    steps: r.path.map((s, k) => ({
      ...brief(g, s),
      step: k === 0 ? 'start' : r.fwd[s] ? 'calls' : 'is called by (against the call)',
    })),
  };
}

/** The shape of the whole map: repositories, sizes and totals. */
export function overview(g) {
  const repos = [];
  for (let r = 0; r < g.R; r++) {
    let svcs = 0;
    for (let d = g.rDs[r]; d < g.rDe[r]; d++) svcs += g.dSe[d] - g.dSs[d];
    repos.push({ ref: refOf('r', r), name: g.repoName[r], domains: g.rDe[r] - g.rDs[r], services: svcs });
  }
  return {
    totals: { repositories: g.R, domains: g.D, services: g.S, endpoints: g.L, contracts: g.C },
    repositories: repos.sort((x, y) => y.services - x.services).slice(0, 30),
  };
}

/** Tool definitions shared by every answerer. `readSource(id)` is supplied by the page when code is available. */
export function toolSet(g, { readSource } = {}) {
  const t = [
    {
      name: 'search',
      description:
        'Find services, endpoints, domains and repositories by name or by what they do. Returns refs to use with the other tools and to cite.',
      inputSchema: {
        type: 'object',
        properties: { query: { type: 'string' }, limit: { type: 'number' } },
        required: ['query'],
      },
      run: input => search(g, input),
    },
    {
      name: 'describe',
      description:
        'Everything known about one item (ref or exact name): summary and where it came from, signature, location, roles, what uses it and what it uses.',
      inputSchema: { type: 'object', properties: { ref: { type: 'string' } }, required: ['ref'] },
      run: input => describe(g, input),
    },
    {
      name: 'impact',
      description:
        'What could break if a service (or an endpoint, through its service) changes: how many services and repositories, nearest first.',
      inputSchema: { type: 'object', properties: { ref: { type: 'string' } }, required: ['ref'] },
      run: input => impact(g, input),
    },
    {
      name: 'route',
      description:
        'How one item reaches another: the chain of services, following calls if possible, otherwise in either direction.',
      inputSchema: {
        type: 'object',
        properties: { from: { type: 'string' }, to: { type: 'string' } },
        required: ['from', 'to'],
      },
      run: input => route(g, input),
    },
    {
      name: 'overview',
      description: 'The shape of the whole codebase: repositories with their sizes, and totals.',
      run: () => overview(g),
    },
  ];
  if (readSource)
    t.push({
      name: 'read_source',
      description:
        'Read the code of one definition (ref), fetched live and not stored. Use only when the summary and signature are not enough.',
      inputSchema: { type: 'object', properties: { ref: { type: 'string' } }, required: ['ref'] },
      run: input => {
        const e = resolve(g, input.ref);
        if (!e || e.t !== 'n') throw new Error('read_source needs a service or endpoint ref.');
        const s = readSource(e.id);
        if (!s) throw new Error('No source available for this item.');
        return { ref: refOf('n', e.id), ...s };
      },
    });
  return t;
}
