/**
 * Graph specs: validate and lay out a real graph given as JSON (docs/GRAPH_SPEC.md), such as Atlas's own code index.
 */
import { finish } from './layout.js';

/**
 * Check a graph spec (see docs/GRAPH_SPEC.md) and return a list of problems; empty when valid.
 * @param {any} spec
 * @returns {string[]}
 */
export function validateSpec(spec) {
  const errs = [];
  if (!spec || !Array.isArray(spec.repos)) return ['spec.repos must be an array'];
  if (!Array.isArray(spec.edges)) errs.push('spec.edges must be an array');
  let services = 0,
    leaves = 0;
  spec.repos.forEach((r, ri) => {
    if (typeof r.name !== 'string') errs.push(`repos[${ri}].name must be a string`);
    if (!Array.isArray(r.domains) || !r.domains.length) errs.push(`repos[${ri}] needs at least one domain`);
    (r.domains || []).forEach((d, di) => {
      if (!Array.isArray(d.services) || !d.services.length)
        errs.push(`repos[${ri}].domains[${di}] needs at least one service`);
      (d.services || []).forEach(s => {
        services++;
        for (const l of s.leaves || []) {
          leaves++;
          if (![1, 2, 3].includes(l.kind)) errs.push(`leaf "${l.name}" has kind ${l.kind}; use 1, 2 or 3`);
        }
      });
    });
  });
  const N = services + leaves;
  (spec.edges || []).forEach((e, i) => {
    if (!Array.isArray(e) || e.length !== 3) {
      errs.push(`edges[${i}] must be [source, target, status]`);
      return;
    }
    const [a, b, st] = e;
    if (!(Number.isInteger(a) && a >= 0 && a < N) || !(Number.isInteger(b) && b >= 0 && b < N))
      errs.push(`edges[${i}] refers to a node outside 0..${N - 1}`);
    if (![0, 1, 2, 3].includes(st)) errs.push(`edges[${i}] has status ${st}; use 0, 1, 2 or 3`);
  });
  return errs.slice(0, 20);
}

/**
 * Flatten repos > domains > services > leaves into contiguous id ranges (services 0..S-1, then leaves S..N-1).
 * @returns hierarchy arrays in the shape model/layout.js `finish` expects
 */
function flattenHierarchy(spec) {
  const repoName = [],
    domName = [],
    svcName = [],
    domRepo = [],
    svcDom = [],
    rDs = [],
    rDe = [],
    dSs = [],
    dSe = [],
    svcLoc = [];
  for (const [r, rp] of spec.repos.entries()) {
    rDs.push(domName.length);
    for (const dm of rp.domains) {
      domName.push(dm.name);
      domRepo.push(r);
      dSs.push(svcName.length);
      for (const sv of dm.services) {
        svcName.push(sv.name);
        svcDom.push(domName.length - 1);
        svcLoc.push(sv.loc || 0);
      }
      dSe.push(svcName.length);
    }
    rDe.push(domName.length);
    repoName.push(rp.name);
  }
  const S = svcName.length,
    leafNames = [],
    kinds = [],
    leafSvc = [],
    leafLoc = [],
    sLs = [],
    sLe = [];
  let i = S;
  for (const rp of spec.repos)
    for (const dm of rp.domains)
      for (const sv of dm.services) {
        sLs.push(i);
        for (const lf of sv.leaves || []) {
          leafNames.push(lf.name);
          kinds.push(lf.kind);
          leafSvc.push(sLs.length - 1);
          leafLoc.push(lf.loc || 0);
          i++;
        }
        sLe.push(i);
      }
  const KND = new Uint8Array(i);
  kinds.forEach((k, j) => (KND[S + j] = k));
  return {
    N: i,
    S,
    L: i - S,
    R: repoName.length,
    D: domName.length,
    domRepo: Uint16Array.from(domRepo),
    rDs: Uint32Array.from(rDs),
    rDe: Uint32Array.from(rDe),
    svcDom: Uint32Array.from(svcDom),
    dSs: Uint32Array.from(dSs),
    dSe: Uint32Array.from(dSe),
    KND,
    leafSvc: Uint32Array.from(leafSvc),
    sLs: Uint32Array.from(sLs),
    sLe: Uint32Array.from(sLe),
    repoName,
    domName,
    svcName,
    leafName: j => leafNames[j - S],
    loc: j => (j < S ? svcLoc[j] : leafLoc[j - S]),
  };
}

/** Edges [source, target, status] as typed arrays. */
function contractsFrom(edges) {
  const CS = new Uint32Array(edges.length),
    CD = new Uint32Array(edges.length),
    CST = new Uint8Array(edges.length);
  edges.forEach(([a, b, st], e) => {
    CS[e] = a;
    CD[e] = b;
    CST[e] = st;
  });
  return { CS, CD, CST };
}

/** Packing weight per service: its size plus half its incoming contracts, so busy services sit central. */
function hubWeights({ S, sLs, sLe, leafSvc }, { CS, CD }) {
  const hub = new Float64Array(S);
  for (let k = 0; k < S; k++) hub[k] = 1 + (sLe[k] - sLs[k]);
  for (let e = 0; e < CS.length; e++) hub[CD[e] < S ? CD[e] : leafSvc[CD[e] - S]] += 0.5;
  return hub;
}

/**
 * Lay out a graph given as a spec (see docs/GRAPH_SPEC.md): real code, or any repo/domain/service/endpoint hierarchy.
 * @param {object} spec
 * @returns {object} laid-out graph (see docs/ARCHITECTURE.md, "The graph object")
 * @throws {Error} listing what is wrong with an invalid spec
 */
export function buildSpec(spec) {
  const problems = validateSpec(spec);
  if (problems.length) throw new Error('Invalid graph spec:\n- ' + problems.join('\n- '));
  const T0 = performance.now();
  const { loc, ...hier } = flattenHierarchy(spec);
  const contracts = contractsFrom(spec.edges);
  const g = finish({ ...hier, ...contracts, hub: hubWeights(hier, contracts), T0 });
  g.meta = spec.meta;
  g.loc = loc;
  return g;
}
