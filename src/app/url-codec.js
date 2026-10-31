/**
 * URL hash codec. Pure: converts between view state and a plain "#name" (letters, digits, hyphens only),
 * the only hash format that survives being shared as an artifact link.
 *
 *   self | 25k                              dataset
 *   -node-<id>                              selected node
 *   -route-<end>-<end>[-avoid][-any][-by<detail>]   end = <serviceId> | r<repoId> | d<domainId> | x (unset)
 *   -issues                                 issues-only mode
 *   -health | -repo                         colour mode chosen by the user
 */
export const SC_NAME = { self: 'self', 281: '281', 5000: '5k', 25000: '25k', 100000: '100k' };
export const SC_NUM = { self: 'self', 281: 281, '5k': 5000, '25k': 25000, '100k': 100000 };

const endToken = e => (!e ? 'x' : e.t === 's' ? String(e.id) : e.t + e.id);
const tokenToEnd = v =>
  v === 'x'
    ? null
    : /^\d+$/.test(v)
      ? { t: 's', id: +v }
      : /^[rd]\d+$/.test(v)
        ? { t: v[0], id: +v.slice(1) }
        : undefined;

/**
 * @param {{dataset:(number|'self'), selectedId:number, route:{from:any,to:any,avoid:boolean,links:string,detail:string,detailSet:boolean}, issuesOnly:boolean, colorMode:string, userColor:boolean}} v
 * @returns {string} hash without the leading "#"
 */
export function formatHash(v) {
  let n = SC_NAME[v.dataset];
  const r = v.route;
  if (r.from || r.to)
    n += `-route-${endToken(r.from)}-${endToken(r.to)}${r.avoid ? '-avoid' : ''}${r.links === 'any' ? '-any' : ''}${r.detailSet ? '-by' + r.detail : ''}`;
  else if (v.selectedId >= 0) n += `-node-${v.selectedId}`;
  if (v.issuesOnly) n += '-issues';
  if (v.userColor) n += '-' + v.colorMode;
  return n;
}

/**
 * @param {string} hash with or without the leading "#"
 * @returns {{n:(number|'self'), node?:number, from?:object|null, to?:object|null, hasRoute?:boolean, avoid?:boolean, any?:boolean, detail?:string, issues?:boolean, color?:string}}
 */
export function parseHash(hash) {
  const p = decodeURIComponent(hash.replace(/^#/, '')).split('-');
  const o = { n: SC_NUM[p[0]] || 'self' };
  for (let i = 1; i < p.length; i++) {
    const t = p[i];
    if (t === 'node') {
      const v = p[++i];
      o.node = /^\d+$/.test(v) ? +v : -1;
    } else if (t === 'route') {
      o.from = tokenToEnd(p[++i]);
      o.to = tokenToEnd(p[++i]);
      o.hasRoute = true;
    } else if (t === 'avoid') o.avoid = true;
    else if (t === 'any') o.any = true;
    else if (/^by(repo|domain|service)$/.test(t)) o.detail = t.slice(2);
    else if (t === 'issues') o.issues = true;
    else if (t === 'health' || t === 'repo') o.color = t;
  }
  return o;
}
