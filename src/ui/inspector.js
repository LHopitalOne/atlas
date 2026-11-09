/**
 * Inspector panel: breadcrumb, title, stats, health, Used by / Depends on / Interfaces lists, actions.
 */
import { expanded, store } from '../state.js';
import { fitNodes, flyTo, flyToTerr } from '../app/camera.js';
import { setRouteEnd } from '../app/route.js';
import { deselect, select } from '../app/selection.js';
import { app, INSP } from '../dom.js';
import { KIND, STATUS } from '../model/vocab.js';
import { copyText } from './feedback.js';
import { BCLS, dotHTML, healthBlock, ICON_X, moreBtn, nameAttrs, pills } from './fragments.js';
import { esc, fmt } from '../util/format.js';
import { aboutHTML, copyForAI, impactHTML } from './about.js';
import { hasSource, openSource } from './code-view.js';
import { toggleImpact } from '../app/focus.js';
import { openLink, toggleHttpImpact } from '../app/http.js';
import { httpSectionHTML, linkInspectorHTML } from './proof.js';

export function openInspector(id) {
  const g = store.G,
    svc = id < g.S,
    s = g.own(id),
    d = g.svcDom[s],
    r = g.domRepo[d];
  let h = `<button class="handle" data-handle aria-label="Resize panel"></button><div class="ins-head"><nav class="crumbs" aria-label="Location" ${nameAttrs}><button data-terr="r${r}">${esc(g.repoName[r])}</button><span class="slash" aria-hidden="true">/</span><button data-terr="d${d}">${esc(g.domName[d])}</button>${svc ? '' : `<span class="slash" aria-hidden="true">/</span><button data-id="${s}">${esc(g.svcName[s])}</button>`}</nav>`;
  h += `<h2 class="ins-title${svc ? '' : ' mono'}" id="insTitle" tabindex="-1" ${nameAttrs}>${esc(g.name(id))}</h2><div class="kindrow"><span class="badge badge-outline">${dotHTML(id)}${KIND[svc ? 0 : g.KND[id]]}</span></div>`;
  const IC = {
    dir: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 1.5l6.5 6.5L8 14.5 1.5 8z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M6 9.5V8a1 1 0 011-1h3M8.6 5.4L10 7 8.6 8.6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    conn: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="2" stroke="currentColor" stroke-width="1.4"/><circle cx="2.8" cy="3.5" r="1.3" stroke="currentColor" stroke-width="1.2"/><circle cx="13.2" cy="4" r="1.3" stroke="currentColor" stroke-width="1.2"/><circle cx="12.5" cy="12.8" r="1.3" stroke="currentColor" stroke-width="1.2"/><path d="M6.4 6.9L3.8 4.4M9.7 7l2.5-2.2M9.5 9.5l2.2 2.3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>',
    copy: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><rect x="5.5" y="5.5" width="8" height="8" rx="1.6" stroke="currentColor" stroke-width="1.4"/><path d="M10.5 3.6V3a1.5 1.5 0 00-1.5-1.5H4A1.5 1.5 0 002.5 3v5A1.5 1.5 0 004 9.5h.6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>',
    source:
      '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M5.5 4.5 2 8l3.5 3.5M10.5 4.5 14 8l-3.5 3.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    ai: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 2.5 9.3 6.7 13.5 8 9.3 9.3 8 13.5 6.7 9.3 2.5 8l4.2-1.3z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>',
  };
  h +=
    `<div class="actions"><button class="act primary" data-route="from" title="Directions from ${esc(g.svcName[s])}. Use the swap button to route here instead.">` +
    `<span class="ic">${IC.dir}</span>Directions</button><button class="act" data-fitconn><span class="ic">${IC.conn}</span>Connections</button><button class="act" data-source${hasSource(id) ? '' : ' disabled title="No source code for this item"'}><span class="ic">${IC.source}</span>Source</button><button class="act" data-copy-ai title="Copy a description of this item for an AI agent"><span class="ic">${IC.ai}</span>Copy for AI</button></div>`;
  h +=
    `<button class="btn btn-ghost btn-icon close" data-close aria-label="Close panel">${ICON_X}</button></div><div class="ins-body scroll">` +
    aboutHTML(id) +
    httpSectionHTML(id);
  const c = [0, 0, 0, 0],
    cap = key => (expanded.has(key) ? 240 : 40);
  if (svc) {
    const outM = new Map(),
      inM = new Map(),
      roots = [id];
    for (let i = g.sLs[id]; i < g.sLe[id]; i++) roots.push(i);
    for (const rt of roots)
      for (let j = g.AO[rt]; j < g.AO[rt + 1]; j++) {
        const e = g.AE[j];
        if (rt !== id && (g.CS[e] === id || g.CD[e] === id)) continue;
        const st = g.CST[e],
          so = g.own(g.CS[e]),
          dt = g.own(g.CD[e]);
        c[st]++;
        const [m, o] = so === id ? [outM, dt] : [inM, so];
        const v = m.get(o) || [0, 0, 0, 0];
        v[st]++;
        m.set(o, v);
      }
    const iss = c[1] + c[2];
    h += `<div class="stats"><div class="stat"><div class="l">Interfaces</div><div class="v">${g.sLe[id] - g.sLs[id]}</div></div><div class="stat"><div class="l">Depends on</div><div class="v">${fmt(outM.size)}</div></div><div class="stat"><div class="l">Used by</div><div class="v">${fmt(inM.size)}</div></div><div class="stat${iss ? ' warn' : ''}"><div class="l">Issues</div><div class="v">${fmt(iss)}</div></div></div>`;
    h += healthBlock(c) + impactHTML(id);
    const list = (title, key, m) => {
      const rows = [...m].sort(
          (a, b) => b[1][2] - a[1][2] || b[1][1] - a[1][1] || b[1][0] + b[1][3] - (a[1][0] + a[1][3]),
        ),
        C = cap(key);
      let o = `<div class="sec"><div class="sec-h"><h3>${title}</h3><span>${fmt(rows.length)}</span></div>`;
      if (!rows.length) o += `<div class="none">No known ${key === 'in' ? 'callers' : 'dependencies'}.</div>`;
      for (const [t, v] of rows.slice(0, C))
        o += `<button class="row" data-id="${t}">${dotHTML(t)}<span class="rn" ${nameAttrs}>${esc(g.svcName[t])}<span class="rs">${esc(g.repoName[g.domRepo[g.svcDom[t]]])}, ${esc(g.domName[g.svcDom[t]])}</span></span><span class="rm">${pills(v)}</span></button>`;
      return o + moreBtn(key, rows.length, C) + `</div>`;
    };
    h += list('Used by', 'in', inM) + list('Depends on', 'out', outM);
    const L = [];
    for (let i = g.sLs[id]; i < g.sLe[id]; i++) L.push(i);
    L.sort((a, b) => g.ISS[b] - g.ISS[a] || g.KND[a] - g.KND[b]);
    h += `<div class="sec"><div class="sec-h"><h3>Interfaces</h3><span>${L.length}</span></div>`;
    for (const i of L) {
      const n = g.AO[i + 1] - g.AO[i];
      h += `<button class="row" data-id="${i}">${dotHTML(i)}<span class="rn mono" ${nameAttrs}>${esc(g.name(i))}</span><span class="rm">${g.ISS[i] ? `<span class="badge ${BCLS[g.ISS[i]]}">${g.ISS[i] === 2 ? 'Unmatched' : 'Ambiguous'}</span>` : ''}<span class="badge badge-secondary" title="Contracts">${n}</span></span></button>`;
    }
    h += `</div>`;
  } else {
    const ins = [],
      outs = [];
    for (let j = g.AO[id]; j < g.AO[id + 1]; j++) {
      const e = g.AE[j];
      c[g.CST[e]]++;
      (g.CS[e] === id ? outs : ins).push(e);
    }
    const iss = c[1] + c[2];
    h += `<div class="stats"><div class="stat"><div class="l">Called by</div><div class="v">${ins.length}</div></div><div class="stat"><div class="l">Calls</div><div class="v">${outs.length}</div></div><div class="stat${iss ? ' warn' : ''}"><div class="l">Issues</div><div class="v">${iss}</div></div><div class="stat"><div class="l">Siblings</div><div class="v">${g.sLe[s] - g.sLs[s]}</div></div></div>`;
    h += healthBlock(c);
    const list = (title, key, L, side) => {
      L.sort((a, b) => (g.CST[b] % 3) - (g.CST[a] % 3));
      const C = cap(key);
      let o = `<div class="sec"><div class="sec-h"><h3>${title}</h3><span>${L.length}</span></div>`;
      if (!L.length)
        o += `<div class="none">${side === 'src' ? 'No known callers.' : 'Calls nothing outside its service.'}</div>`;
      for (const e of L.slice(0, C)) {
        const t = side === 'src' ? g.CS[e] : g.CD[e],
          st = g.CST[e];
        o += `<button class="row" data-id="${t}">${dotHTML(t)}<span class="rn${t >= g.S ? ' mono' : ''}" ${nameAttrs}>${esc(g.name(t))}<span class="rs">${t >= g.S ? esc(g.svcName[g.own(t)]) : esc(g.repoName[g.domRepo[g.svcDom[t]]])}</span></span><span class="rm"><span class="badge ${BCLS[st]}">${st === 3 ? 'Inferred' : STATUS[st]}</span></span></button>`;
      }
      return o + moreBtn(key, L.length, C) + `</div>`;
    };
    h += list('Called by', 'in', ins, 'src') + list('Calls', 'out', outs, 'dst');
  }
  INSP.innerHTML = h + `</div>`;
  app.classList.add('has-insp');
}

/** Show the proof of HTTP link group gid in the inspector. */
export function openLinkInspector(gid) {
  INSP.innerHTML = linkInspectorHTML(gid);
  app.classList.add('has-insp');
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  INSP.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) return deselect(true);
    if (e.target.closest('[data-handle]')) return INSP.classList.toggle('tall');
    if (e.target.closest('[data-fitconn]'))
      return flyTo(fitNodes(store.focusList.length ? store.focusList : [store.selectedId], 2.4));
    const mb = e.target.closest('[data-more]');
    if (mb) {
      expanded.add(mb.dataset.more);
      const sc = INSP.querySelector('.ins-body').scrollTop;
      if (store.selectedId >= 0) openInspector(store.selectedId);
      INSP.querySelector('.ins-body').scrollTop = sc;
      return;
    }
    const rb = e.target.closest('[data-route]');
    if (rb) return setRouteEnd(rb.dataset.route, { t: 's', id: store.G.own(store.selectedId) });
    if (e.target.closest('[data-copy-ai]'))
      return copyText(copyForAI(store.selectedId), `Copied ${store.G.name(store.selectedId)} for AI`);
    const src = e.target.closest('[data-source]');
    if (src && !src.disabled) return openSource(store.selectedId, src);
    if (e.target.closest('[data-impact]')) return toggleImpact(store.selectedId);
    const hi = e.target.closest('[data-http-impact]');
    if (hi) return toggleHttpImpact(hi.dataset.httpImpact);
    const lk = e.target.closest('[data-link]');
    if (lk) return openLink(+lk.dataset.link, 'list');
    const tb = e.target.closest('[data-terr]');
    if (tb) {
      const v = tb.dataset.terr;
      deselect();
      return flyToTerr(v[0], +v.slice(1));
    }
    const t = e.target.closest('[data-id]');
    if (t) select(+t.dataset.id, 'list');
  });
}
