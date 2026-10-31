/**
 * Command-palette search: repositories, domains, services, endpoints, recent items and quick actions.
 */
import { route, store } from '../state.js';
import { fitAll, flyToTerr } from '../app/camera.js';
import { setRouteEnd } from '../app/route.js';
import { deselect, select } from '../app/selection.js';
import { Q, RES } from '../dom.js';
import { css, theme } from '../render/theme.js';
import { setMode, toggleIssues } from './controls.js';
import { startDirections } from './directions.js';
import { announce } from './feedback.js';
import { dotHTML, nameAttrs } from './fragments.js';
import { $ } from '../util/dom.js';
import { esc, fmt } from '../util/format.js';

let hits = [];
let act = 0;
export function buildIndex() {
  const g = store.G,
    a = [];
  for (let r = 0; r < g.R; r++) a.push(['r', r, g.repoName[r]]);
  for (let d = 0; d < g.D; d++) a.push(['d', d, g.domName[d]]);
  for (let i = 0; i < g.N; i++) a.push(['n', i, g.name(i)]);
  // summaries make search work by meaning ("handles refunds"), not only by name
  const about = a.map(x => (x[0] === 'n' && g.doc ? (g.doc(x[1]) || '').toLowerCase() : ''));
  store.IDX = { items: a, low: a.map(x => x[2].toLowerCase()), about };
}
export function score(s, q) {
  const i = s.indexOf(q);
  if (i >= 0) return 1000 - i * 3 - s.length * 0.4 + (i === 0 ? 150 : 0);
  let j = 0,
    gaps = 0,
    last = -1;
  for (let c = 0; c < s.length && j < q.length; c++)
    if (s[c] === q[j]) {
      if (last >= 0) gaps += c - last - 1;
      last = c;
      j++;
    }
  return j === q.length ? 400 - gaps * 5 - s.length * 0.4 : -1;
}
export function loadRecent() {
  try {
    store.recent = JSON.parse(localStorage.getItem('atlas-recent-' + store.G.src) || '[]')
      .filter(i => Number.isInteger(i) && i >= 0 && i < store.G.N)
      .slice(0, 5);
  } catch (_) {
    store.recent = [];
  }
}
export function pushRecent(id) {
  store.recent = [id, ...store.recent.filter(x => x !== id)].slice(0, 5);
  try {
    localStorage.setItem('atlas-recent-' + store.G.src, JSON.stringify(store.recent));
  } catch (_) {}
}
const ACTIONS = () => [
  { label: store.issuesOnly ? 'Show all contracts' : 'Show only issues', kbd: 'I', run: () => toggleIssues() },
  {
    label: `Colour by ${store.colorMode === 'health' ? 'repository' : 'health'}`,
    kbd: 'C',
    run: () => {
      store.userColor = true;
      setMode(store.colorMode === 'health' ? 'repo' : 'health');
    },
  },
  { label: 'Get directions', kbd: 'D', run: () => startDirections() },
  { label: 'Fit to screen', kbd: 'F', run: () => fitAll() },
];
const GROUP = h =>
  h[0] === 'a'
    ? 'Actions'
    : h[0] === 'm'
      ? 'By what it does'
      : h[0] === 'h'
        ? 'Recent'
        : h[0] === 'r'
          ? 'Repositories'
          : h[0] === 'd'
            ? 'Domains'
            : h[1] < store.G.S
              ? 'Services'
              : 'Endpoints';
/** Items whose summary contains every word of the query (3+ letters), excluding those already found by name. */
function meaningHits(q, byName) {
  const words = q.split(/\s+/).filter(w => w.length >= 3);
  if (!words.length) return [];
  const { items, about } = store.IDX,
    out = [];
  for (let i = 0; i < items.length && out.length < 60; i++)
    if (about[i] && !byName.has(i) && words.every(w => about[i].includes(w))) out.push([about[i].length, i]);
  return out
    .sort((a, b) => a[0] - b[0])
    .slice(0, 6)
    .map(([, i]) => ['m', items[i][1], items[i][2]]);
}

/** Summary snippet with the query words marked. */
function snippet(text, q) {
  const words = q.split(/\s+/).filter(w => w.length >= 3);
  const lower = text.toLowerCase(),
    at = Math.max(0, Math.min(...words.map(w => lower.indexOf(w)).filter(i => i >= 0)) - 24);
  let t = (at ? '…' : '') + text.slice(at, at + 110) + (text.length > at + 110 ? '…' : '');
  let html = esc(t);
  for (const w of words)
    html = html.replace(new RegExp(w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), m => `<mark>${m}</mark>`);
  return html;
}

function runSearch() {
  if (!store.G) return;
  const q = Q.value.trim().toLowerCase();
  if (!q) {
    hits = store.recent.map(id => ['h', id, store.G.name(id)]).concat(ACTIONS().map((x, i) => ['a', i, x.label]));
    act = 0;
    drawResults('');
    return;
  }
  if (!store.IDX) buildIndex();
  const top = [];
  const it = store.IDX.items,
    lo = store.IDX.low;
  for (let i = 0; i < it.length; i++) {
    let sc = score(lo[i], q);
    if (sc < 0) continue;
    const t = it[i][0];
    sc += t === 'r' ? 140 : t === 'd' ? 110 : it[i][1] < store.G.S ? 90 : 0;
    if (top.length < 10 || sc > top[top.length - 1][0]) {
      top.push([sc, i]);
      top.sort((a, b) => b[0] - a[0]);
      if (top.length > 10) top.pop();
    }
  }
  const meaning = meaningHits(q, new Set(top.map(x => x[1])));
  const order = ['Repositories', 'Domains', 'Services', 'Endpoints', 'By what it does', 'Actions'];
  ACTIONS().forEach((x, i) => {
    if (x.label.toLowerCase().includes(q)) top.push([0, -1, ['a', i, x.label]]);
  });
  hits = top
    .map(x => (x[1] < 0 ? x[2] : it[x[1]]))
    .concat(meaning)
    .sort((a, b) => order.indexOf(GROUP(a)) - order.indexOf(GROUP(b)));
  act = 0;
  drawResults(q);
}
function closeResults() {
  RES.hidden = true;
  Q.setAttribute('aria-expanded', 'false');
  Q.removeAttribute('aria-activedescendant');
  hits = [];
}
function drawResults(q) {
  RES.hidden = false;
  Q.setAttribute('aria-expanded', 'true');
  const g = store.G;
  if (!hits.length) {
    RES.innerHTML = `<div class="cmd-empty">Nothing matches “${esc(q)}”. Try a service name or a path such as /odds.</div>`;
    Q.removeAttribute('aria-activedescendant');
    return;
  }
  let h = '',
    last = '';
  const ret = `<span class="kbd ret" aria-hidden="true">↵</span>`;
  hits.forEach(([t, id, nm], n) => {
    const grp = GROUP([t, id]);
    if (grp !== last) {
      h += `<div class="cmd-h" role="presentation">${grp}</div>`;
      last = grp;
    }
    if (t === 'a') {
      const ax = ACTIONS()[id];
      h += `<div class="cmd-item" role="option" id="opt-${n}" data-n="${n}" aria-selected="${n === act}"><span class="ico" aria-hidden="true"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="nm">${esc(nm)}</span><span class="hint">${ax.kbd ? `<span class="kbd" aria-label="Shortcut ${ax.kbd}">${ax.kbd}</span>` : ''}${ret}</span></div>`;
      return;
    }
    if (t === 'h') id = +id;
    if (t === 'm') {
      h += `<div class="cmd-item two" role="option" id="opt-${n}" data-n="${n}" aria-selected="${n === act}">${dotHTML(id)}<span class="nm2"><span class="nm${id >= g.S ? ' mono' : ''}" ${nameAttrs}>${esc(nm)}</span><span class="desc">${snippet(g.doc(id), q)}</span></span><span class="hint">${ret}</span></div>`;
      return;
    }
    const p = q ? nm.toLowerCase().indexOf(q) : -1;
    const lab =
      p >= 0
        ? esc(nm.slice(0, p)) + '<mark>' + esc(nm.slice(p, p + q.length)) + '</mark>' + esc(nm.slice(p + q.length))
        : esc(nm);
    const glyph =
      t === 'n' || t === 'h'
        ? dotHTML(id)
        : `<span class="g tr" style="--c:${css(t === 'r' && store.repoRank[id] < 5 && store.colorMode === 'repo' ? theme.pal[store.repoRank[id]] : theme.muted)}" aria-hidden="true"></span>`;
    const sub =
      t === 'r'
        ? `${fmt(g.rDe[id] - g.rDs[id])} domains`
        : t === 'd'
          ? esc(g.repoName[g.domRepo[id]])
          : id < g.S
            ? esc(g.domName[g.svcDom[id]])
            : esc(g.svcName[g.own(id)]);
    h += `<div class="cmd-item" role="option" id="opt-${n}" data-n="${n}" aria-selected="${n === act}">${glyph}<span class="nm${(t === 'n' || t === 'h') && id >= g.S ? ' mono' : ''}" ${nameAttrs}>${lab}</span><span class="hint"><span class="sub" ${nameAttrs}>${sub}</span>${ret}</span></div>`;
  });
  RES.innerHTML = h;
  Q.setAttribute('aria-activedescendant', 'opt-' + act);
}
function choose(n) {
  const [t, id] = hits[n];
  Q.value = '';
  closeResults();
  if (t === 'a') {
    Q.blur();
    ACTIONS()[id].run();
    return;
  }
  if (t === 'n' || t === 'h' || t === 'm') {
    if (route.picking) {
      Q.blur();
      setRouteEnd(route.picking, { t: 's', id: store.G.own(id) });
    } else select(id, 'search');
  } else if (route.picking) {
    Q.blur();
    setRouteEnd(route.picking, { t, id });
  } else {
    Q.blur();
    deselect();
    flyToTerr(t, id);
    announce(
      `Showing ${t === 'r' ? 'repository' : 'domain'} ${t === 'r' ? store.G.repoName[id] : store.G.domName[id]}.`,
    );
  }
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  Q.addEventListener('input', runSearch);
  Q.addEventListener('focus', runSearch);
  Q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!hits.length) return;
      act = (act + (e.key === 'ArrowDown' ? 1 : -1) + hits.length) % hits.length;
      drawResults(Q.value.trim().toLowerCase());
      $('#opt-' + act)?.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter' && hits.length) {
      e.preventDefault();
      choose(act);
    } else if (e.key === 'Escape') {
      if (Q.value) {
        Q.value = '';
        closeResults();
      } else {
        closeResults();
        Q.blur();
      }
    }
  });
  RES.addEventListener('pointerdown', e => {
    const b = e.target.closest('.cmd-item');
    if (b) {
      e.preventDefault();
      choose(+b.dataset.n);
    }
  });
  document.addEventListener('pointerdown', e => {
    if (!e.target.closest('.search')) closeResults();
  });
}
