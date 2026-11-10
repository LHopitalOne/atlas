/**
 * HTTP links between repositories (spec.links, see docs/GRAPH_SPEC.md): the proof of each link, links grouped by the
 * line they draw (caller to endpoint), and what calls an endpoint, a file or a repository from other repositories,
 * which is what breaks if it changes. Pure; runs in Node.
 */

/** How sure a link is, strongest first. `note` says what the badge means, in the words the panels use. */
export const PROOF = {
  scip: {
    label: 'Confirmed by SCIP',
    cls: 'badge-scip',
    note: 'Every name the link rests on resolves, in a SCIP index of the code, to the definition the finder assumed.',
  },
  syntax: {
    label: 'Read from syntax',
    cls: 'badge-syntax',
    note: 'The method and path are written at the call site: there is no name to resolve, so nothing for SCIP to check.',
  },
  matched: {
    label: 'Matched',
    cls: 'badge-secondary',
    note: 'Read from the code, but no SCIP index could check the names it rests on.',
  },
  inferred: {
    label: 'Inferred',
    cls: 'badge-inferred',
    note: 'The route fits only under an assumption the code does not show, such as a base URL prefix.',
  },
  ambiguous: {
    label: 'Ambiguous',
    cls: 'badge-warning',
    note: 'More than one route could take this request.',
  },
  contradicted: {
    label: 'Contradicted by SCIP',
    cls: 'badge-destructive',
    note: 'SCIP resolves a name this link rests on to a different definition than the finder assumed.',
  },
  outside: {
    label: 'Outside service',
    cls: 'badge-outline',
    note: 'Sent to a host none of these repositories serves: a third-party API, a CDN, an analytics or ad script, or a site a visitor is linked to.',
  },
};
export const PROOF_ORDER = ['scip', 'syntax', 'matched', 'inferred', 'ambiguous', 'contradicted', 'outside'];

/** A link to a host none of the repositories serves. */
export const isOutside = l => l.proof === 'outside';
const rank = p => {
  const i = PROOF_ORDER.indexOf(p);
  return i < 0 ? PROOF_ORDER.length : i;
};

/** Problems with spec.links / spec.unmatched (empty when valid or absent). */
export function validateLinks(spec, N) {
  const errs = [],
    node = v => Number.isInteger(v) && v >= 0 && v < N,
    repo = v => Number.isInteger(v) && v >= 0 && v < spec.repos.length;
  if (spec.links === undefined) return errs;
  if (!Array.isArray(spec.links)) return ['spec.links must be an array'];
  spec.links.forEach((l, i) => {
    if (!l || !node(l.from) || !node(l.to)) errs.push(`links[${i}] needs from and to node ids in 0..${N - 1}`);
    else if (!PROOF[l.proof]) errs.push(`links[${i}] has proof ${l.proof}; use ${PROOF_ORDER.join(', ')}`);
    else if (!l.call || !l.route || !repo(l.call.repo) || !repo(l.route.repo))
      errs.push(`links[${i}] needs call and route sites with a repo index`);
  });
  if (spec.unmatched !== undefined && !Array.isArray(spec.unmatched)) errs.push('spec.unmatched must be an array');
  return errs;
}

const repoOf = (g, i) => g.domRepo[g.svcDom[g.own(i)]];

/** The contract drawn from a to b, or -1. */
function contractOf(g, a, b) {
  for (let j = g.AO[a]; j < g.AO[a + 1]; j++) {
    const e = g.AE[j];
    if (g.CS[e] === a && g.CD[e] === b) return e;
  }
  return -1;
}

/**
 * Index a spec's HTTP links on a laid-out graph.
 * @returns {{links:object[], groups:{from:number,to:number,e:number,links:number[],proof:string}[],
 *   byFrom:Map<number,number[]>, byTo:Map<number,number[]>, repos:{url:string,commit:string}[],
 *   unmatched:object[], accuracy:object|null}}
 */
export function httpIndex(spec, g) {
  const links = spec.links || [],
    at = new Map(),
    groups = [];
  links.forEach((l, i) => {
    const key = l.from + '>' + l.to;
    if (!at.has(key)) {
      at.set(key, groups.length);
      const within = l.call.repo === l.route.repo;
      groups.push({ from: l.from, to: l.to, e: contractOf(g, l.from, l.to), links: [], proof: l.proof, within });
    }
    const gr = groups[at.get(key)];
    gr.links.push(i);
    if (rank(l.proof) < rank(gr.proof)) gr.proof = l.proof;
  });
  const byFrom = new Map(),
    byTo = new Map(),
    push = (m, k, v) => (m.has(k) ? m.get(k).push(v) : m.set(k, [v]));
  groups.forEach((gr, i) => {
    push(byFrom, gr.from, i);
    push(byTo, gr.to, i);
  });
  return {
    links,
    groups,
    byFrom,
    byTo,
    repos: spec.repos.map(r => ({ url: r.url || '', commit: r.commit || '' })),
    unmatched: spec.unmatched || [],
    accuracy: (spec.meta && spec.meta.accuracy) || null,
  };
}

/** GitHub (or other forge) link to a cited line at the pinned commit, or '' when the spec has no address. */
export function siteUrl(H, site) {
  const r = H.repos[site.repo];
  if (!r || !r.url || !r.commit) return '';
  const path = site.file.split('/').map(encodeURIComponent).join('/');
  return `${r.url}/blob/${r.commit}/${path}#L${site.line}`;
}

/** Group ids whose endpoint is node id, or (for a service) any of its leaves; or that end in repository r. */
export function groupsInto(g, H, target) {
  const out = [];
  if (target.t === 'r') {
    H.groups.forEach((gr, i) => {
      if (repoOf(g, gr.to) === target.id && repoOf(g, gr.from) !== target.id) out.push(i);
    });
    return out;
  }
  const id = target.id,
    ids = id < g.S ? [id, ...range(g.sLs[id], g.sLe[id])] : [id];
  for (const n of ids) for (const i of H.byTo.get(n) || []) out.push(i);
  return out;
}

/** Group ids that start at node id or, for a service, at any of its leaves. */
export function groupsFrom(g, H, id) {
  const ids = id < g.S ? [id, ...range(g.sLs[id], g.sLe[id])] : [id],
    out = [];
  for (const n of ids) for (const i of H.byFrom.get(n) || []) out.push(i);
  return out;
}

function range(a, b) {
  const out = [];
  for (let i = a; i < b; i++) out.push(i);
  return out;
}

/**
 * What breaks if an endpoint, service or repository changes: the call sites in other repositories that send it
 * requests (each with its proof), the endpoints they reach, and the caller services.
 * `within` counts the call sites in the target's own repository; `repos` are the other repositories.
 * @returns {{groups:number[], links:number[], within:number, endpoints:number[], callers:number[], repos:number[]}}
 */
export function httpImpact(g, H, target) {
  const groups = groupsInto(g, H, target),
    links = [],
    endpoints = new Set(),
    callers = new Set(),
    repos = new Set();
  let within = 0;
  for (const i of groups) {
    const gr = H.groups[i];
    links.push(...gr.links);
    if (gr.within) within += gr.links.length;
    endpoints.add(gr.to);
    callers.add(g.own(gr.from));
    if (!gr.within) repos.add(repoOf(g, gr.from));
  }
  return { groups, links, within, endpoints: [...endpoints], callers: [...callers], repos: [...repos] };
}

/** Links between each ordered pair of repositories: [{a, b, groups}]. */
export function repoPairs(g, H) {
  const m = new Map();
  H.groups.forEach((gr, i) => {
    const l = H.links[gr.links[0]],
      a = l.call.repo,
      b = l.route.repo,
      k = a + '>' + b;
    if (!m.has(k)) m.set(k, { a, b, groups: [] });
    m.get(k).groups.push(i);
  });
  // between repositories first, busiest first; links inside one repository last
  return [...m.values()].sort(
    (x, y) => (x.a === x.b) - (y.a === y.b) || y.groups.length - x.groups.length || x.a - y.a || x.b - y.b,
  );
}

/** A link inside one repository (its frontend calling its own API, a task for its own workers) rather than between two. */
export const isWithin = l => l.call.repo === l.route.repo;

const WITHIN = {
  request: {
    short: 'frontend → API',
    long: 'Browser code calling its own repository’s routes.',
    paren: 'a frontend calling its own API',
  },
  task: {
    short: 'tasks → its workers',
    long: 'Background tasks and queue messages handed to the same repository’s workers.',
    paren: 'tasks sent to its own workers',
  },
  mixed: {
    short: 'calls to itself',
    long: 'Browser code calling its own routes, and tasks handed to its own workers.',
    paren: 'a frontend calling its own API, or tasks sent to its own workers',
  },
};

/** What links inside one repository are, in words: a frontend calling its API, tasks for its workers, or both. */
export function withinKind(links) {
  const tasks = links.filter(l => l.protocol === 'task' || l.protocol === 'amqp').length;
  return WITHIN[tasks === 0 ? 'request' : tasks === links.length ? 'task' : 'mixed'];
}

/** How many links between repositories have each proof: {scip: 30, syntax: 4, ...}. */
export function proofCounts(H) {
  const c = {};
  for (const l of H.links) if (!isWithin(l)) c[l.proof] = (c[l.proof] || 0) + 1;
  return c;
}

/** How a protocol is named on the page; one not listed is shown in capitals. */
export const PROTOCOL_NAMES = {
  http: 'HTTP',
  websocket: 'WebSocket',
  grpc: 'gRPC',
  graphql: 'GraphQL',
  kafka: 'Kafka',
  amqp: 'AMQP',
  redis: 'Redis',
  tcp: 'TCP',
  udp: 'UDP',
  task: 'Task queue',
};
export const protocolName = p => PROTOCOL_NAMES[p] || String(p).toUpperCase();

/** How many links (between repositories and inside one) go over each protocol, most first: [['http', 34], ...]. */
export function protocolCounts(H) {
  const c = new Map();
  for (const l of H.links) c.set(l.protocol || 'http', (c.get(l.protocol || 'http') || 0) + 1);
  return [...c].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
}

/** Control point of the arc drawn for an HTTP link (shared by the overlay and picking, so hits match the drawing). */
export function arcCtrl(x0, y0, x1, y1) {
  const dx = x1 - x0,
    dy = y1 - y0;
  return [(x0 + x1) / 2 - dy * 0.18, (y0 + y1) / 2 + dx * 0.18];
}

/** Distance from point (px, py) to the quadratic arc between two screen points, sampled in `steps` pieces. */
export function arcDistance(px, py, x0, y0, x1, y1, steps = 24) {
  const [cx, cy] = arcCtrl(x0, y0, x1, y1);
  let best = Infinity,
    ax = x0,
    ay = y0;
  for (let s = 1; s <= steps; s++) {
    const t = s / steps,
      u = 1 - t,
      bx = u * u * x0 + 2 * u * t * cx + t * t * x1,
      by = u * u * y0 + 2 * u * t * cy + t * t * y1;
    best = Math.min(best, segDist(px, py, ax, ay, bx, by));
    ax = bx;
    ay = by;
  }
  return best;
}

function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax,
    dy = by - ay,
    L = dx * dx + dy * dy,
    t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0;
  return Math.hypot(px - ax - t * dx, py - ay - t * dy);
}
