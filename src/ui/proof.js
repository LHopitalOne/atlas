/**
 * HTTP links as HTML: a link's proof (the line that sends the request and the route line that serves it, each with
 * its code, file:line and a GitHub link at the pinned commit), proof badges, what SCIP checked, the accuracy measured
 * on an answer key, and the HTTP sections of a node's inspector (served here, called from, sends, impact).
 */
import { store } from '../state.js';
import { groupsFrom, groupsInto, httpImpact, PROOF, siteUrl } from '../model/http.js';
import { impactOf } from '../graph/insights.js';
import { dotHTML, ICON_X, nameAttrs } from './fragments.js';
import { esc, fmt } from '../util/format.js';

const plural = (n, one, many) => `${fmt(n)} ${n === 1 ? one : many}`;

/** A badge for a proof, with what it means as its tooltip. */
export const proofBadge = p =>
  `<span class="badge ${PROOF[p].cls}" title="${esc(PROOF[p].note)}">${esc(PROOF[p].label)}</span>`;

/** The few lines of code around a cited line, the cited line marked. */
function codeHTML(site) {
  if (!site.code || !site.code.length) return '';
  const indents = site.code.filter(t => t.trim()).map(t => t.length - t.trimStart().length),
    cut = indents.length ? Math.min(...indents) : 0;
  const rows = site.code.map((t, k) => {
    t = t.slice(cut);
    const n = site.start + k;
    return `<span class="pl${n === site.line ? ' hit' : ''}"><span class="ln" aria-hidden="true">${n}</span>${esc(t) || ' '}</span>`;
  });
  return `<pre class="pcode" tabindex="0" aria-label="Code around line ${site.line}"><code>${rows.join('')}</code></pre>`;
}

/** One end of a link: repository, file:line with its GitHub link, the function or handler, and the code. */
function siteHTML(g, site, title, detail) {
  const url = siteUrl(g.http, site);
  return (
    `<div class="site"><div class="site-h"><span class="site-t">${title}</span><span class="site-r" ${nameAttrs}>${esc(g.repoName[site.repo])}</span></div>` +
    `<div class="site-loc"><span class="mono" ${nameAttrs}>${esc(site.file)}:${site.line}</span>${url ? `<a class="linkbtn" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="Open this line on GitHub at the commit the map was built from">GitHub ↗</a>` : ''}</div>` +
    (detail ? `<div class="site-fn">${detail}</div>` : '') +
    codeHTML(site) +
    '</div>'
  );
}

const callDetail = c => (c.function ? `in <code ${nameAttrs}>${esc(c.function)}</code>` : '');
const routeDetail = r =>
  r.handler
    ? `handled by <code ${nameAttrs}>${esc(r.handler)}</code>${r.framework ? ` · ${esc(r.framework)}` : ''}`
    : esc(r.framework || '');

/** What SCIP said about each name the link rests on. */
function checksHTML(checks) {
  if (!checks || !checks.length) return '';
  const rows = checks
    .map(
      c =>
        `<li><code ${nameAttrs}>${esc(c.name)}</code> at <span class="mono">${esc(c.at)}</span> means <span class="mono">${esc(c.means)}</span> <span class="badge ${c.verdict === 'confirmed' ? 'badge-scip' : c.verdict === 'contradicted' ? 'badge-destructive' : 'badge-secondary'}">${esc(c.verdict)}</span></li>`,
    )
    .join('');
  return `<div class="checks"><div class="site-t">What SCIP checked</div><ul>${rows}</ul></div>`;
}

/** The inspector for an HTTP link group: both ends, every call site, the proof, and the endpoint's impact. */
export function linkInspectorHTML(gid) {
  const g = store.G,
    H = g.http,
    gr = H.groups[gid],
    first = H.links[gr.links[0]],
    a = first.call.repo,
    b = first.route.repo;
  let h = `<button class="handle" data-handle aria-label="Resize panel"></button><div class="ins-head"><nav class="crumbs" aria-label="Repositories" ${nameAttrs}><button data-terr="r${a}">${esc(g.repoName[a])}</button><span class="slash" aria-hidden="true">→</span><button data-terr="r${b}">${esc(g.repoName[b])}</button></nav>`;
  h += `<h2 class="ins-title mono" id="insTitle" tabindex="-1" ${nameAttrs}>${esc(first.method)} ${esc(first.path)}</h2><div class="kindrow">${proofBadge(gr.proof)}<span class="badge badge-outline">${gr.within ? 'Inside one repository' : 'HTTP link'}</span></div>`;
  h += `<button class="btn btn-ghost btn-icon close" data-close aria-label="Close panel">${ICON_X}</button></div><div class="ins-body scroll">`;
  h += `<div class="about"><p class="about-text">${esc(PROOF[gr.proof].note)}</p><div class="prov">Why it matched: ${esc(first.reason || 'the method and path fit one route')}${gr.within ? '. No answer key covers links inside one repository yet.' : ''}</div></div>`;
  for (const li of gr.links) {
    const l = H.links[li];
    h += `<div class="sec proof">${siteHTML(g, l.call, 'Sends the request', callDetail(l.call))}`;
    h += `<div class="hop" aria-hidden="true"><span>↓</span><span class="mono">${esc(l.method)} ${esc(l.path)}</span></div>`;
    if (li === gr.links[0]) h += siteHTML(g, l.route, 'Serves it', routeDetail(l.route));
    h += checksHTML(l.checks) + '</div>';
  }
  h += `<div class="sec"><div class="sec-h"><h3>Ends</h3></div>${nodeRow(g, gr.from)}${nodeRow(g, gr.to)}</div>`;
  h += impactBlockHTML(g, { t: 'n', id: gr.to }, 'this endpoint');
  return h + '</div>';
}

function nodeRow(g, i) {
  const repo = g.repoName[g.domRepo[g.svcDom[g.own(i)]]];
  return `<button class="row" data-id="${i}">${dotHTML(i)}<span class="rn${i >= g.S ? ' mono' : ''}" ${nameAttrs}>${esc(g.name(i))}<span class="rs">${esc(repo)} · ${esc(g.svcName[g.own(i)])}</span></span><span class="rm"></span></button>`;
}

/** A row for a link group: the far end, its repository and its proof. */
export function groupRow(g, gid, side) {
  const H = g.http,
    gr = H.groups[gid],
    l = H.links[gr.links[0]],
    far = side === 'caller' ? gr.from : gr.to,
    farRepo = g.repoName[side === 'caller' ? l.call.repo : l.route.repo],
    title = side === 'caller' ? l.call.function || g.name(far) : `${l.method} ${l.path}`,
    sub =
      side === 'caller'
        ? `${farRepo} · ${l.call.file}:${l.call.line}`
        : `${farRepo} · ${l.route.handler || g.name(far)}`,
    n = gr.links.length > 1 ? `<span class="badge badge-secondary" title="Call sites">${gr.links.length}</span>` : '';
  return `<button class="row" data-link="${gid}"><span class="g ev" style="--c:var(--route)" aria-hidden="true"></span><span class="rn mono" ${nameAttrs}>${esc(title)}<span class="rs">${esc(sub)}</span></span><span class="rm">${n}${proofBadge(gr.proof)}</span></button>`;
}

/** What a change would break, with a toggle that lights it up on the map. */
export function impactBlockHTML(g, target, what) {
  const H = g.http,
    im = httpImpact(g, H, target);
  if (!im.groups.length) return '';
  const key = target.t + target.id,
    on = store.httpImpact === key,
    reach = new Set();
  for (const s of im.callers) for (const t of impactOf(g, s).services) if (!im.callers.includes(t)) reach.add(t);
  const cross = im.links.length - im.within,
    parts = [];
  if (cross)
    parts.push(
      `<b>${plural(cross, 'call site', 'call sites')}</b> in <b>${plural(im.repos.length, 'other repository', 'other repositories')}</b>`,
    );
  if (im.within) parts.push(`<b>${plural(im.within, 'call site', 'call sites')}</b> in its own frontend`);
  let h = `<div class="sec"><div class="sec-h"><h3>If ${esc(what)} changes</h3></div><div class="impact-body"><p class="impact-text">`;
  h += `${parts.join(' and ')} send ${target.t === 'n' && target.id >= g.S ? 'it' : 'them'} requests, from <b>${plural(im.callers.length, 'file', 'files')}</b>`;
  h += target.t === 'n' && target.id < g.S ? ` to ${plural(im.endpoints.length, 'endpoint', 'endpoints')}.` : '.';
  if (reach.size)
    h += ` Another <b>${plural(reach.size, 'file', 'files')}</b> reach those calls through Graphify’s call graph (inferred, not proven).`;
  return (
    h +
    `</p><button class="btn btn-outline btn-sm" data-http-impact="${key}" aria-pressed="${on}">${on ? 'Hide on map' : 'Show on map'}</button></div></div>`
  );
}

/** The HTTP sections of a node's inspector: the route an endpoint serves and its callers, a file's endpoints, the
 * requests a function or file sends to other repositories, and impact. Empty for nodes no link touches. */
export function httpSectionHTML(id) {
  const g = store.G,
    H = g.http;
  if (!H) return '';
  let h = '';
  const into = groupsInto(g, H, { t: 'n', id }),
    from = groupsFrom(g, H, id);
  if (id >= g.S && H.byTo.has(id)) {
    const l = H.links[H.groups[into[0]].links[0]];
    h += `<div class="sec proof"><div class="sec-h"><h3>HTTP endpoint</h3></div>${siteHTML(g, l.route, 'Served at', routeDetail(l.route))}</div>`;
  }
  if (into.length)
    h += `<div class="sec"><div class="sec-h"><h3>Called over HTTP from</h3><span>${fmt(into.length)}</span></div>${into.map(i => groupRow(g, i, 'caller')).join('')}</div>`;
  if (from.length)
    h += `<div class="sec"><div class="sec-h"><h3>Sends requests to</h3><span>${fmt(from.length)}</span></div>${from.map(i => groupRow(g, i, 'endpoint')).join('')}</div>`;
  if (into.length) h += impactBlockHTML(g, { t: 'n', id }, id < g.S ? 'this file’s endpoints' : 'this endpoint');
  return h;
}

/** How the links scored on an answer key built without the tool; says so plainly when nothing was measured. */
export function accuracyHTML(acc, within = 0) {
  if (!acc)
    return `<div class="acc"><div class="acc-h">Accuracy not measured</div><p class="acc-note">No answer key exists for these repositories, so these links are unchecked.</p></div>`;
  const stat = (v, label) => `<div class="acc-s"><b>${esc(v)}</b><span>${esc(label)}</span></div>`;
  let h = `<div class="acc"><div class="acc-h">Measured on an answer key built without the tool</div><div class="acc-stats">`;
  h += stat(`${acc.found}/${acc.of}`, 'production links found');
  h += stat(acc.falseLinks, acc.falseLinks === 1 ? 'false link' : 'false links');
  if (acc.scip !== undefined) h += stat(`${acc.scip}/${acc.found}`, 'of them confirmed by SCIP');
  h += '</div>';
  if (acc.how) h += `<p class="acc-note">${esc(acc.how)}</p>`;
  if (acc.missed) h += `<p class="acc-note">Missed: ${esc(acc.missed)}</p>`;
  if (within)
    h += `<p class="acc-note">Not counted: ${fmt(within)} links inside one repository (a frontend calling its own API), which no answer key covers yet.</p>`;
  if (acc.key)
    h += `<a class="linkbtn acc-link" href="${esc(acc.key)}" target="_blank" rel="noopener noreferrer">The answer key and how it was built ↗</a>`;
  return h + '</div>';
}
