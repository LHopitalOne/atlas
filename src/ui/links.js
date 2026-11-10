/**
 * HTTP links panel: how the links scored on an answer key, every link between repositories grouped by direction
 * (click one for its proof), what calls each repository (shown on the map), and the requests no route was found for.
 * It is the home panel of maps that have links: it opens with them, and steps aside while Ask, Directions or Needs
 * attention is open.
 */
import { store } from '../state.js';
import { openLink, toggleHttpImpact } from '../app/http.js';
import { select } from '../app/selection.js';
import { LINKS } from '../dom.js';
import { httpImpact, isOutside, isWithin, PROOF_ORDER, proofCounts, repoPairs, withinKind } from '../model/http.js';
import { renderAttn, syncLegend } from './attention.js';
import { closeAsk } from './ask.js';
import { ICON_X, nameAttrs } from './fragments.js';
import { accuracyHTML, groupRow, proofBadge } from './proof.js';
import { $ } from '../util/dom.js';
import { esc, fmt } from '../util/format.js';

let closedByUser = false;

/** Open the panel when a map with links loads, unless the viewer closed it. */
export function autoOpenLinks() {
  if (store.G && store.G.http && !closedByUser) openLinksPanel();
  else renderLinks();
}

export function openLinksPanel() {
  closeAsk();
  if (store.attnOpen) {
    store.attnOpen = false;
    renderAttn();
  }
  store.linksOpen = true;
  closedByUser = false;
  renderLinks();
}

export function closeLinksPanel() {
  store.linksOpen = false;
  closedByUser = true;
  renderLinks();
}

/** Toggle the panel (the dock button and the L shortcut). */
export const toggleLinksPanel = () => (store.linksOpen ? closeLinksPanel() : openLinksPanel());

function headerHTML(g, H) {
  const cross = H.links.filter(l => !isWithin(l) && !isOutside(l)),
    repos = new Set(cross.flatMap(l => [l.call.repo, l.route.repo])),
    within = H.links.filter(isWithin).length,
    outside = H.links.filter(isOutside).length,
    parts = [
      cross.length ? `${fmt(cross.length)} requests between ${fmt(repos.size)} repositories` : '',
      within ? `${fmt(within)} inside one repository` : '',
      outside ? `${fmt(outside)} to outside services` : '',
    ].filter(Boolean),
    said =
      parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}` : parts[0] || 'No links';
  return `<div class="ph"><div><h2 id="linksTitle">HTTP links</h2><p>${said}, each proven down to the line</p></div><button class="btn btn-ghost btn-icon" data-lclose aria-label="Close HTTP links">${ICON_X}</button></div>`;
}

function proofLegendHTML(H) {
  const c = proofCounts(H);
  return `<div class="proof-legend">${PROOF_ORDER.filter(p => c[p])
    .map(p => `<span>${proofBadge(p)}<b>${fmt(c[p])}</b></span>`)
    .join('')}</div>`;
}

function pairsHTML(g, H) {
  let h = '';
  for (const p of repoPairs(g, H)) {
    const sites = p.groups.reduce((n, i) => n + H.groups[i].links.length, 0),
      rows = p.groups.map(i => groupRow(g, i, 'endpoint')).join('');
    if (p.a === p.b) {
      // inside one repository (a frontend calling its own API, tasks for its workers): many, no answer key, so folded
      const kind = withinKind(p.groups.flatMap(i => H.groups[i].links.map(j => H.links[j])));
      h += `<details class="sec unmatched within"><summary class="sec-h"><h3 ${nameAttrs}>Inside ${esc(g.repoName[p.a])}: ${esc(kind.short)}</h3><span>${fmt(sites)}</span></summary><p class="impact-text pad">${esc(kind.long)} No answer key covers these yet, so they are not in the accuracy above.</p>${rows}</details>`;
    } else
      h += `<div class="sec"><div class="sec-h"><h3 ${nameAttrs}>${esc(g.repoName[p.a])} → ${esc(g.repoName[p.b])}</h3><span>${fmt(sites)}</span></div>${rows}</div>`;
  }
  return h;
}

function repoImpactHTML(g, H) {
  let rows = '';
  for (let r = 0; r < g.R; r++) {
    const im = httpImpact(g, H, { t: 'r', id: r });
    if (!im.groups.length) continue;
    const key = 'r' + r,
      on = store.httpImpact === key,
      callers = im.repos.map(x => g.repoName[x]).join(', ');
    rows += `<div class="imp-row"><span class="rn" ${nameAttrs}><b>${esc(g.repoName[r])}</b><span class="rs">${fmt(im.endpoints.length)} endpoints, ${fmt(im.links.length)} call sites in ${esc(callers)}</span></span><button class="btn btn-outline btn-sm" data-http-impact="${key}" data-label="Show" aria-pressed="${on}">${on ? 'Hide on map' : 'Show'}</button></div>`;
  }
  return rows ? `<div class="sec"><div class="sec-h"><h3>What breaks if a service changes</h3></div>${rows}</div>` : '';
}

function unmatchedHTML(g, H) {
  if (!H.unmatched.length) return '';
  const rows = H.unmatched
    .map(
      u =>
        `<button class="row" data-id="${u.from}"><span class="g ev" style="--c:var(--destructive)" aria-hidden="true"></span><span class="rn mono" ${nameAttrs}>${esc(u.method)} ${esc(u.path)}<span class="rs">${esc(g.repoName[u.call.repo])} · ${esc(u.call.file)}:${u.call.line} · ${esc(u.reason)}</span></span><span class="rm"></span></button>`,
    )
    .join('');
  return `<details class="sec unmatched"><summary class="sec-h"><h3>Requests with no route found</h3><span>${fmt(H.unmatched.length)}</span></summary><p class="impact-text pad">Not drawn as links: no route on this map has their path, or several could take them. One with no route may be code left behind when an endpoint was removed, or be served by code that is not on the map.</p>${rows}</details>`;
}

/** Render the panel for the current map (hidden on maps without links). */
export function renderLinks() {
  const g = store.G,
    H = g && g.http,
    btn = $('#linksBtn');
  if (btn) {
    btn.hidden = !H;
    btn.setAttribute('aria-pressed', String(!!(H && store.linksOpen)));
  }
  const show = !!H && store.linksOpen;
  LINKS.classList.toggle('on', show);
  syncLegend();
  if (!show) return;
  LINKS.innerHTML =
    headerHTML(g, H) +
    `<div class="scroll" style="padding:0 8px 10px">${accuracyHTML(H.accuracy, H.links.filter(isWithin))}${proofLegendHTML(H)}${pairsHTML(g, H)}${repoImpactHTML(g, H)}${unmatchedHTML(g, H)}</div>`;
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  LINKS.addEventListener('click', e => {
    if (e.target.closest('[data-lclose]')) return closeLinksPanel();
    const hi = e.target.closest('[data-http-impact]');
    if (hi) return toggleHttpImpact(hi.dataset.httpImpact);
    const lk = e.target.closest('[data-link]');
    if (lk) return openLink(+lk.dataset.link, 'list');
    const t = e.target.closest('[data-id]');
    if (t) select(+t.dataset.id, 'list');
  });
  const btn = $('#linksBtn');
  if (btn) btn.addEventListener('click', toggleLinksPanel);
}
