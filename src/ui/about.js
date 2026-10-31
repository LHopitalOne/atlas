/**
 * "About" block in the inspector: what an item does (and where that text came from), its roles in the graph,
 * its signature and location, how far a change reaches, and a plain-text version of all of it for AI agents.
 */
import { store } from '../state.js';
import { KIND } from '../model/vocab.js';
import { impactOf, rolesOf } from '../graph/insights.js';
import { hasSource } from './code-view.js';
import { esc, fmt } from '../util/format.js';

/** Where the summary text came from, shown under it so people (and agents) know how far to trust it. */
function provenance(g) {
  const m = g.meta || {};
  if (m.docSource === 'comment') return `From a doc comment in the code · commit ${esc(m.commit || '')}`;
  if (m.docSource === 'simulated') return 'AI summary · simulated for this demo data';
  return 'From the graph spec';
}

const ROLE_ICON = { entry: '→', hub: '✳', bridge: '⇄', deadEnd: '■', isolated: '○' };

/** Summary, roles, signature and location. */
export function aboutHTML(id) {
  const g = store.G,
    doc = g.doc ? g.doc(id) : '',
    sig = g.sig ? g.sig(id) : '',
    loc = g.loc ? g.loc(id) : '';
  let h = '<div class="about">';
  h += doc
    ? `<p class="about-text">${esc(doc)}</p><div class="prov">${provenance(g)}</div>`
    : `<p class="about-text none">No description in the code yet.</p><div class="prov">In the product, an AI summary would appear here, marked as AI-written.</div>`;
  if (id < g.S) {
    const roles = rolesOf(g, id);
    if (roles.length)
      h += `<div class="roles">${roles.map(r => `<span class="role role-${r.key}" title="${esc(r.detail)}"><span aria-hidden="true">${ROLE_ICON[r.key]}</span>${esc(r.label)}<span class="sr-only">: ${esc(r.detail)}</span></span>`).join('')}</div>`;
  }
  if (sig) h += `<pre class="sig"><code>${esc(sig)}</code></pre>`;
  if (typeof loc === 'string' && loc)
    h += `<div class="locrow"><span class="mono">${esc(loc)}</span>${hasSource(id) ? '<button class="linkbtn" data-source>View source</button>' : ''}</div>`;
  return h + '</div>';
}

/** How far a change to service id reaches, with a toggle to light it up on the map. */
export function impactHTML(id) {
  const g = store.G;
  if (id >= g.S) return '';
  const im = impactOf(g, id),
    n = im.services.length,
    on = store.impactId === id;
  let h = '<div class="sec"><div class="sec-h"><h3>Impact</h3></div>';
  if (!n) return h + '<p class="impact-text">Nothing calls it, so a change here stays here.</p></div>';
  h += `<p class="impact-text">Changing this can affect <b>${fmt(n)}</b> service${n === 1 ? '' : 's'} in <b>${fmt(im.repos)}</b> repositor${im.repos === 1 ? 'y' : 'ies'}: ${fmt(im.direct)} ${im.direct === 1 ? 'calls' : 'call'} it directly${n > im.direct ? ', the rest through them' : ''}.</p>`;
  return (
    h +
    `<button class="btn btn-outline btn-sm" data-impact aria-pressed="${on}">${on ? 'Hide on map' : 'Show on map'}</button></div>`
  );
}

const listOf = a =>
  a.length ? a.slice(0, 25).join(', ') + (a.length > 25 ? `, and ${a.length - 25} more` : '') : 'none';

/** Name, kind, place in the hierarchy, source location and summary. */
function identityLines(g, id) {
  const s = g.own(id),
    d = g.svcDom[s],
    r = g.domRepo[d],
    svc = id < g.S;
  const L = [
    `# ${g.name(id)} (${svc ? KIND[0] : KIND[g.KND[id]]})`,
    `Location: ${g.repoName[r]} > ${g.domName[d]}${svc ? '' : ` > ${g.svcName[s]}`}`,
  ];
  const loc = g.loc ? g.loc(id) : '',
    end = g.end ? g.end(id) : 0,
    commit = g.meta && g.meta.commit;
  if (typeof loc === 'string' && loc) L.push(`Source: ${loc}${end ? `-${end}` : ''}${commit ? ` @ ${commit}` : ''}`);
  const doc = g.doc ? g.doc(id) : '',
    simulated = g.meta && g.meta.docSource === 'simulated';
  L.push(`Summary: ${doc ? `${doc} (${simulated ? 'simulated' : 'from the code'})` : 'none in the code'}`);
  if (g.sig && g.sig(id)) L.push('Signature: `' + g.sig(id) + '`');
  return L;
}

/** Roles, impact and connections of a service. */
function serviceLines(g, id, named) {
  const L = [],
    roles = rolesOf(g, id),
    im = impactOf(g, id),
    usedBy = [],
    dependsOn = [];
  if (roles.length) L.push(`Roles: ${roles.map(x => `${x.label}: ${x.detail}`).join('; ')}`);
  L.push(
    `Impact: a change can affect ${im.services.length} services in ${im.repos} repositories (${im.direct} direct caller${im.direct === 1 ? '' : 's'}).`,
  );
  for (let j = g.QO[id]; j < g.QO[id + 1]; j++) usedBy.push(named(g.dr.a[g.QI[j]]));
  for (let j = g.RO[id]; j < g.RO[id + 1]; j++) dependsOn.push(named(g.dr.b[g.RI[j]]));
  return [...L, `Used by: ${listOf(usedBy)}`, `Depends on: ${listOf(dependsOn)}`];
}

/** Callers and callees of an endpoint. */
function leafLines(g, id, named) {
  const calledBy = [],
    calls = [];
  for (let j = g.AO[id]; j < g.AO[id + 1]; j++) {
    const e = g.AE[j],
      out = g.CS[e] === id;
    (out ? calls : calledBy).push(named(out ? g.CD[e] : g.CS[e]));
  }
  return [`Called by: ${listOf(calledBy)}`, `Calls: ${listOf(calls)}`];
}

/** The selected item as Markdown for an AI agent: identity, purpose, role, impact, connections, location, link. */
export function copyForAI(id) {
  const g = store.G,
    named = t => `${g.name(t)} (${g.repoName[g.domRepo[g.svcDom[g.own(t)]]]})`;
  const issues = g.ISS[id] === 2 ? 'has an unmatched contract' : g.ISS[id] === 1 ? 'has an ambiguous contract' : 'none';
  return [
    ...identityLines(g, id),
    ...(id < g.S ? serviceLines(g, id, named) : leafLines(g, id, named)),
    `Issues: ${issues}`,
    `Map link: ${location.href}`,
  ].join('\n');
}
