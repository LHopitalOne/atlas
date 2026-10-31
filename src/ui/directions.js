/**
 * Directions panel: start and destination fields with suggestions, Follow and Detail controls, the route summary,
 * a legend for the line styles, notes on weak links, and the step list. Rendering is split into small HTML builders.
 */
import { route, store } from '../state.js';
import { fitNodes, flyTo, flyToTerr } from '../app/camera.js';
import { computeRoute, endName, routeSteps, setRouteEnd, stepName } from '../app/route.js';
import { deselect, select } from '../app/selection.js';
import { writeHash } from '../app/url.js';
import { RT } from '../dom.js';
import { callerCount } from '../graph/route-search.js';
import { STATUS } from '../model/vocab.js';
import { requestRender } from '../render/frame.js';
import { css, theme } from '../render/theme.js';
import { renderAttn } from './attention.js';
import { BCLS, dotHTML, ICON_X, nameAttrs } from './fragments.js';
import { buildIndex, score } from './search.js';
import { esc, fmt } from '../util/format.js';

export function startDirections() {
  if (!store.G) return;
  if (store.selectedId >= 0 && !route.from && !route.picking)
    setRouteEnd('from', { t: 's', id: store.G.own(store.selectedId) });
  else {
    route.picking = route.from ? 'to' : 'from';
    renderRoute();
  }
  focusRouteField();
}
export function focusRouteField() {
  const el = RT.querySelector(`.rt-in[data-which="${route.picking || (route.from ? 'to' : 'from')}"]`);
  if (el) {
    el.focus();
    el.select();
  }
}
/** Directions panel: built from small pieces, each returning HTML (all dynamic text goes through esc). */
const fieldHTML = (end, which) =>
  `<input class="rt-in${route.picking === which ? ' picking' : ''}" data-which="${which}" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="rtSug" aria-label="${which === 'from' ? 'Start' : 'Destination'}" placeholder="${which === 'from' ? 'Start: repo, domain or service…' : 'Destination…'}" value="${esc(endName(end))}" autocomplete="off" spellcheck="false" ${nameAttrs}>`;
const radioHTML = (attr, cur, opts) =>
  opts
    .map(
      ([v, l]) =>
        `<button role="radio" data-${attr}="${v}" aria-checked="${cur === v}" tabindex="${cur === v ? 0 : -1}">${l}</button>`,
    )
    .join('');

function headerHTML() {
  return `<div class="ph"><h2>Directions</h2><button class="btn btn-ghost btn-icon" data-rclose aria-label="Close directions">${ICON_X}</button></div>`;
}
function fieldsHTML() {
  let h = '';
  h += `<div class="lp-body"><div class="rt-fields"><span class="rt-pin a" aria-hidden="true"></span>${fieldHTML(route.from, 'from')}<button class="btn btn-ghost btn-icon rt-swap" data-swap aria-label="Swap start and destination"><svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M5 2v11M5 13l-3-3M5 13l3-3M11 14V3M11 3l-3 3M11 3l3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button><span class="rt-pin b" aria-hidden="true"></span>${fieldHTML(route.to, 'to')}</div><div class="rt-sug" id="rtSug" role="listbox" aria-label="Suggestions" hidden></div>`;
  return h;
}
function controlsHTML() {
  let h = '';
  h += `<div class="rt-ctl"><div class="rt-row"><span class="rt-lab" id="lblLinks">Follow</span><div class="toggle-group" role="radiogroup" aria-labelledby="lblLinks">${radioHTML(
    'links',
    route.links,
    [
      ['calls', 'Calls only'],
      ['any', 'Either direction'],
    ],
  )}</div></div>`;
  h += `<div class="rt-row"><span class="rt-lab" id="lblDetail">Detail</span><div class="toggle-group" role="radiogroup" aria-labelledby="lblDetail">${radioHTML(
    'detail',
    route.detail,
    [
      ['repo', 'Repos'],
      ['domain', 'Domains'],
      ['service', 'Services'],
    ],
  )}</div></div>`;
  h += `<label class="chk"><input type="checkbox" id="avoid"${route.avoid ? ' checked' : ''}> Avoid unmatched contracts</label></div>`;
  return h;
}
/** Hop count, what the route passes through, and which link types it crosses. */
function summaryHTML(g) {
  let h = '';
  const reposCrossed = new Set(route.path.map(s => g.domRepo[g.svcDom[s]])).size,
    domsCrossed = new Set(route.path.map(s => g.svcDom[s])).size;
  const cnt = s => route.hops.filter(x => x.st === s).length,
    un = cnt(2),
    amb = cnt(1),
    inf = cnt(3),
    back = route.hops.filter(x => !x.fwd).length,
    notes = [];
  if (un) notes.push(`${un} ${STATUS[2].toLowerCase()}`);
  if (amb) notes.push(`${amb} ${STATUS[1].toLowerCase()}`);
  if (inf) notes.push(`${inf} ${STATUS[3].toLowerCase()}`);
  h += `<div class="rt-sum"><div class="big">${route.hops.length} ${route.hops.length === 1 ? 'hop' : 'hops'}</div><div class="sm">Through ${reposCrossed} ${reposCrossed === 1 ? 'repository' : 'repositories'} and ${domsCrossed} ${domsCrossed === 1 ? 'domain' : 'domains'}${back ? `, ${back} backward` : ''}. ${notes.length ? 'Crosses ' + notes.join(', ') + (un + amb + inf === 1 ? ' link.' : ' links.') : 'Every link is ' + STATUS[0].toLowerCase() + '.'}</div></div>`;
  return h;
}
/** What solid lines, dashed lines and moving dots mean. */
function legendHTML() {
  let h = '';
  const ln = dash =>
    `<svg width="30" height="8" viewBox="0 0 30 8" aria-hidden="true"><path d="M1 4h28" stroke="${css(theme.route)}" stroke-width="1.6"${dash ? ' stroke-dasharray="3.5 3"' : ''} stroke-linecap="round"/><circle cx="${dash ? 9 : 21}" cy="4" r="2.2" fill="${css(theme.route)}" stroke="${css(theme.halo)}" stroke-width="1"/></svg>`;
  h += `<div class="rt-legend" role="note" aria-label="How to read the route"><div class="lg">${ln(false)}<span><b>Solid</b>: the step calls the next one. The route follows the call.</span></div>`;
  h += `<div class="lg">${ln(true)}<span><b>Dashed</b>: backwards. The next step calls the previous one, so the route goes against the call.</span></div>`;
  h += `<div class="lg"><span style="justify-self:center;width:6px;height:6px;border-radius:50%;background:${css(theme.route)}"></span><span>Moving dots show the direction of travel, from start to destination.</span></div></div>`;
  return h;
}
/** Explain backward steps: two things joined only through something they share is a weak connection. */
function noteHTML(g) {
  let h = '';
  const why = [],
    whyCaller = [],
    big = Math.max(8, Math.round(g.S * 0.05)),
    callers = s => callerCount(g, s);
  for (let i = 0; i + 1 < route.hops.length; i++) {
    const h1 = route.hops[i],
      h2 = route.hops[i + 1],
      piv = h1.b,
      prv = g.svcName[h1.a],
      nxt = g.svcName[h2.b],
      pn = `${g.svcName[piv]} (${g.domName[g.svcDom[piv]]})`;
    if (h1.fwd && !h2.fwd) {
      const n = callers(piv);
      why.push(
        `<b>${esc(prv)}</b> and <b>${esc(nxt)}</b> are joined only because both use <b>${esc(pn)}</b>${n >= big ? `, which ${fmt(n)} services use` : ''}. That doesn’t mean one depends on the other.`,
      );
    } else if (!h1.fwd && h2.fwd)
      whyCaller.push(
        `<b>${esc(prv)}</b> and <b>${esc(nxt)}</b> are joined only because <b>${esc(pn)}</b> uses both. That doesn’t mean one depends on the other.`,
      );
  }
  if (!why.length && whyCaller.length) why.push(...whyCaller);
  if (route.note || why.length)
    h += `<div class="rt-note">${route.note ? esc(route.note) : ''}${why.length ? `<ul>${why.map(w => `<li ${nameAttrs}>${w}</li>`).join('')}</ul>` : ''}${why.length ? `<div style="margin-top:6px">Treat this route as a weak connection.</div>` : ''}</div>`;
  return h;
}
function stepsHTML(g) {
  const steps = routeSteps();
  let h = '';
  h += `<div class="rt-steps" role="list">`;
  steps.forEach(st => {
    const hop = st.hop >= 0 ? route.hops[st.hop] : null;
    let detail = '<span>Start</span>';
    if (hop) {
      const callee = hop.e >= 0 ? g.CD[hop.e] : -1;
      const how = hop.fwd
        ? '↓ called by the previous step' + (callee >= g.S ? ', via ' + esc(g.name(callee)) : '')
        : '↑ calls the previous step';
      detail = `<span class="badge ${BCLS[hop.st]}">${hop.st === 3 ? 'Inferred' : STATUS[hop.st]}</span><span ${nameAttrs}>${how}</span>`;
    }
    const inner =
      st.n > 1 ? ` <span style="color:var(--muted-foreground);font-weight:400">· ${st.n} services</span>` : '';
    h += `<button class="step" role="listitem" data-key="${st.key}"${st.hop >= 0 ? ` data-hop="${st.hop}"` : ''}><span class="rail" aria-hidden="true"><i${hop && !hop.fwd ? ' style="background:transparent;box-shadow:0 0 0 2px var(--route) inset,0 0 0 3px var(--card)"' : ''}></i></span><span><span class="sn" ${nameAttrs}>${esc(stepName(st))}${inner}</span><span class="sd">${detail}</span></span></button>`;
  });
  h += `</div>`;
  return h;
}

/** Render the Directions panel for the current route state. */
export function renderRoute() {
  const g = store.G;
  const on = !!route.from || !!route.to || !!route.picking;
  RT.classList.toggle('on', on);
  renderAttn();
  if (!on) return;
  let h = headerHTML() + fieldsHTML() + controlsHTML();
  if (route.picking)
    h += `<div class="rt-sum"><div class="sm">Type a repository, domain, service or endpoint, or click one on the map.</div></div>`;
  else if (route.msg) h += `<div class="rt-sum"><div class="sm">${esc(route.msg)}</div></div>`;
  else if (route.hops.length) h += summaryHTML(g) + legendHTML() + noteHTML(g) + stepsHTML(g);
  RT.innerHTML = h + `</div>`;
}
/* directions fields: type-ahead over services and endpoints (an endpoint routes via its service) */
let rtHits = [];
let rtAct = 0;
let rtWhich = null;
let rtBlurTO = 0;
const rtSug = () => RT.querySelector('#rtSug');
function rtSuggest(inp) {
  const g = store.G,
    q = inp.value.trim().toLowerCase();
  rtWhich = inp.dataset.which;
  route.picking = rtWhich;
  RT.querySelectorAll('.rt-in').forEach(x => x.classList.toggle('picking', x === inp));
  if (!store.IDX) buildIndex();
  let list = [];
  if (!q) {
    const seen = new Set();
    for (const i of store.recent) {
      const s = g.own(i);
      if (!seen.has(s)) {
        seen.add(s);
        list.push(['n', s, g.svcName[s], 'Recent']);
      }
    }
    for (const r of g.repoOrder.slice(0, 8)) list.push(['r', r, g.repoName[r], 'Repositories']);
  } else {
    const top = [];
    for (let i = 0; i < store.IDX.items.length; i++) {
      const it = store.IDX.items[i];
      let sc = score(store.IDX.low[i], q);
      if (sc < 0) continue;
      sc += it[0] === 'r' ? 140 : it[0] === 'd' ? 110 : it[1] < g.S ? 90 : 0;
      top.push([sc, i]);
    }
    top.sort((a, b) => b[0] - a[0]);
    const seen = new Set();
    for (const [, i] of top) {
      const it = store.IDX.items[i];
      if (it[0] === 'n') {
        const s = g.own(it[1]);
        if (seen.has('s' + s)) continue;
        seen.add('s' + s);
      }
      list.push([...it, null]);
      if (list.length >= 8) break;
    }
  }
  rtHits = list;
  rtAct = 0;
  drawRtSug(q);
}
function drawRtSug(q) {
  const g = store.G,
    box = rtSug(),
    inp = RT.querySelector(`.rt-in[data-which="${rtWhich}"]`);
  if (!box || !inp) return;
  if (!rtHits.length && !q) {
    box.hidden = true;
    inp.setAttribute('aria-expanded', 'false');
    return;
  }
  box.hidden = false;
  inp.setAttribute('aria-expanded', 'true');
  if (!rtHits.length) {
    box.innerHTML = `<div class="cmd-empty">Nothing matches “${esc(q)}”.</div>`;
    inp.removeAttribute('aria-activedescendant');
    return;
  }
  let last = '';
  box.innerHTML = rtHits
    .map(([t, id, nm, grp], n) => {
      let head = '';
      if (grp && grp !== last) {
        head = `<div class="cmd-h" role="presentation">${grp}</div>`;
        last = grp;
      }
      const p = q ? nm.toLowerCase().indexOf(q) : -1;
      const lab =
        p >= 0
          ? esc(nm.slice(0, p)) + '<mark>' + esc(nm.slice(p, p + q.length)) + '</mark>' + esc(nm.slice(p + q.length))
          : esc(nm);
      const glyph =
        t === 'n'
          ? dotHTML(id)
          : `<span class="g tr" style="--c:${css(t === 'r' && store.repoRank[id] < 5 && store.colorMode === 'repo' ? theme.pal[store.repoRank[id]] : theme.muted)}" aria-hidden="true"></span>`;
      const sub =
        t === 'r'
          ? 'Repository'
          : t === 'd'
            ? 'Domain in ' + esc(g.repoName[g.domRepo[id]])
            : id < g.S
              ? esc(g.domName[g.svcDom[id]])
              : 'on ' + esc(g.svcName[g.own(id)]);
      return (
        head +
        `<div class="cmd-item" role="option" id="rtopt-${n}" data-n="${n}" aria-selected="${n === rtAct}">${glyph}<span class="nm${t === 'n' && id >= g.S ? ' mono' : ''}" ${nameAttrs}>${lab}</span><span class="hint"><span class="sub" ${nameAttrs}>${sub}</span><span class="kbd ret" aria-hidden="true">↵</span></span></div>`
      );
    })
    .join('');
  inp.setAttribute('aria-activedescendant', 'rtopt-' + rtAct);
}
function rtChoose(n) {
  const h = rtHits[n];
  if (!h) return;
  const box = rtSug();
  if (box) box.hidden = true;
  setRouteEnd(rtWhich, h[0] === 'n' ? { t: 's', id: store.G.own(h[1]) } : { t: h[0], id: h[1] });
}
const hopHL = e => {
  const s = e.target.closest('[data-hop]');
  const v = s ? +s.dataset.hop : -1;
  if (v !== route.hl) {
    route.hl = v;
    requestRender();
  }
};

/** Wire this module to the DOM. Called once from main.js. */
function onClick(e) {
  if (e.target.closest('[data-rclose]')) {
    route.from = route.to = null;
    route.picking = null;
    route.detailSet = false;
    computeRoute();
    renderRoute();
    requestRender();
    writeHash();
    return;
  }
  if (e.target.closest('[data-swap]')) {
    [route.from, route.to] = [route.to, route.from];
    route.picking = !route.from ? 'from' : !route.to ? 'to' : null;
    computeRoute();
    renderRoute();
    requestRender();
    writeHash();
    return;
  }
  const lk = e.target.closest('[data-links]');
  if (lk) {
    route.links = lk.dataset.links;
    computeRoute();
    renderRoute();
    if (route.path.length > 1) flyTo(fitNodes(route.path, 2));
    requestRender();
    writeHash();
    RT.querySelector(`[data-links="${route.links}"]`)?.focus();
    return;
  }
  const dt = e.target.closest('[data-detail]');
  if (dt) {
    route.detail = dt.dataset.detail;
    route.detailSet = true;
    renderRoute();
    writeHash();
    RT.querySelector(`[data-detail="${route.detail}"]`)?.focus();
    return;
  }
  const s = e.target.closest('.step');
  if (s) {
    route.hl = -1;
    const t = s.dataset.key[0],
      id = +s.dataset.key.slice(1);
    if (t === 's') select(id, 'list');
    else {
      deselect();
      flyToTerr(t, id);
    }
  }
}

function onKeydown(e) {
  const b = e.target.closest('[data-links],[data-detail]');
  if (!b || !['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
  e.preventDefault();
  e.stopPropagation();
  const sib = [...b.parentElement.children],
    i = sib.indexOf(b),
    n = sib[(i + (e.key === 'ArrowRight' ? 1 : -1) + sib.length) % sib.length];
  n.click();
}

function onInput(e) {
  if (e.target.classList.contains('rt-in')) rtSuggest(e.target);
}

function onFocusin(e) {
  if (e.target.classList.contains('rt-in')) {
    clearTimeout(rtBlurTO);
    rtSuggest(e.target);
  }
}

function onFocusout(e) {
  if (!e.target.classList.contains('rt-in')) return;
  rtBlurTO = setTimeout(() => {
    if (RT.contains(document.activeElement) && document.activeElement.classList.contains('rt-in')) return;
    const box = rtSug();
    if (box) box.hidden = true;
    e.target.value = endName(e.target.dataset.which === 'from' ? route.from : route.to);
    e.target.setAttribute('aria-expanded', 'false');
  }, 150);
}

function onKeydown2(e) {
  const inp = e.target;
  if (!inp.classList || !inp.classList.contains('rt-in')) return;
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (!rtHits.length) return;
    rtAct = (rtAct + (e.key === 'ArrowDown' ? 1 : -1) + rtHits.length) % rtHits.length;
    drawRtSug(inp.value.trim().toLowerCase());
    RT.querySelector('#rtopt-' + rtAct)?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (rtHits.length) rtChoose(rtAct);
  } else if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    const box = rtSug();
    if (box) box.hidden = true;
    inp.blur();
  }
}

function onPointerdown(e) {
  const it = e.target.closest('#rtSug .cmd-item');
  if (it) {
    e.preventDefault();
    rtChoose(+it.dataset.n);
  }
}

function onChange(e) {
  if (e.target.id === 'avoid') {
    route.avoid = e.target.checked;
    computeRoute();
    renderRoute();
    requestRender();
    writeHash();
  }
}

function onPointerleave() {
  route.hl = -1;
  requestRender();
}

/** Wire the panel to the DOM. Called once from main.js. */
export function init() {
  RT.addEventListener('click', onClick);
  RT.addEventListener('keydown', onKeydown);
  RT.addEventListener('input', onInput);
  RT.addEventListener('focusin', onFocusin);
  RT.addEventListener('focusout', onFocusout);
  RT.addEventListener('keydown', onKeydown2);
  RT.addEventListener('pointerdown', onPointerdown);
  RT.addEventListener('change', onChange);
  RT.addEventListener('pointerover', hopHL);
  RT.addEventListener('focusin', hopHL);
  RT.addEventListener('pointerleave', onPointerleave);
}
