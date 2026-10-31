/**
 * Source view: a wider panel beside the inspector with the lines of the selected definition.
 * In the product the lines are fetched from GitHub at view time, at the indexed commit, with the viewer's own access,
 * and never stored. In this prototype they come from a source bundle embedded in the page (`meta.sourceBundle`).
 */
import { store } from '../state.js';
import { $ } from '../util/dom.js';
import { esc } from '../util/format.js';

const CONTEXT = 3,
  MAX_LINES = 160;
let bundle = null,
  bundleId = null,
  openId = -1,
  opener = null;
const tokenCache = new Map();

/** The source bundle for the current graph, if it has one. */
function sources() {
  const id = store.G && store.G.meta && store.G.meta.sourceBundle;
  if (!id) return null;
  if (bundleId !== id) {
    const el = document.getElementById(id);
    try {
      bundle = el ? JSON.parse(el.textContent) : null;
    } catch (_) {
      bundle = null;
    }
    bundleId = id;
    tokenCache.clear();
  }
  return bundle;
}

/** Where an item's source is: file, first and last line. */
function locate(id) {
  const g = store.G,
    loc = g.loc ? g.loc(id) : '';
  if (typeof loc !== 'string' || !loc.includes(':')) return null;
  const i = loc.lastIndexOf(':'),
    file = loc.slice(0, i),
    start = +loc.slice(i + 1);
  return { file, start, end: Math.max(start, (g.end && g.end(id)) || start) };
}

/** Whether "View source" can show anything for this item. */
export function hasSource(id) {
  const b = sources(),
    at = locate(id);
  return !!(b && at && b.files[at.file] !== undefined);
}

// a light JavaScript highlighter: comments, strings, numbers, keywords (enough for reading, not a parser)
const JS_TOKENS =
  /(\/\*[\s\S]*?\*\/|\/\/[^\n]*)|('(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\[\s\S]|[^`\\])*`)|\b(\d[\d_.]*(?:e[+-]?\d+)?)\b|\b(import|export|from|const|let|var|function|return|if|else|for|while|do|of|in|new|class|extends|this|null|undefined|true|false|typeof|instanceof|try|catch|finally|throw|break|continue|switch|case|default|async|await)\b/g;
const CLS = [null, 'c', 's', 'n', 'k'];

/** HTML for every line of a file, highlighted once and cached. */
function linesOf(file, text) {
  if (tokenCache.has(file)) return tokenCache.get(file);
  const out = [];
  let cur = '';
  const push = (str, cls) => {
    const parts = str.split('\n');
    parts.forEach((p, i) => {
      if (i) {
        out.push(cur);
        cur = '';
      }
      if (p) cur += cls ? `<span class="t${cls}">${esc(p)}</span>` : esc(p);
    });
  };
  if (/\.js$/.test(file)) {
    let last = 0,
      m;
    JS_TOKENS.lastIndex = 0;
    while ((m = JS_TOKENS.exec(text))) {
      push(text.slice(last, m.index));
      push(m[0], CLS[[1, 2, 3, 4].find(k => m[k] !== undefined)]);
      last = m.index + m[0].length;
    }
    push(text.slice(last));
  } else push(text);
  out.push(cur);
  tokenCache.set(file, out);
  return out;
}

/** Open the source of item id beside the inspector. */
export function openSource(id, from) {
  const b = sources(),
    at = locate(id),
    panel = $('#code');
  if (!b || !at || b.files[at.file] === undefined) return;
  const lines = linesOf(at.file, b.files[at.file]);
  const first = Math.max(1, at.start - CONTEXT),
    last = Math.min(lines.length, at.end + CONTEXT, first + MAX_LINES - 1);
  let rows = '';
  for (let n = first; n <= last; n++)
    rows += `<div class="ln${n >= at.start && n <= at.end ? ' def' : ''}"><span class="no" aria-hidden="true">${n}</span><span class="tx">${lines[n - 1] || ' '}</span></div>`;
  const cut =
    at.end + CONTEXT > last
      ? `<div class="cut">Showing ${last - first + 1} lines; the definition continues to line ${at.end}.</div>`
      : '';
  panel.innerHTML = `<div class="cv-head"><div class="cv-title"><span class="mono">${esc(at.file)}</span><span class="cv-range">lines ${at.start}–${at.end}</span></div>
    <button class="btn btn-ghost btn-icon" data-cv-close aria-label="Close source"><svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></button></div>
    <div class="cv-prov" title="In this prototype the source is bundled with the page. The product fetches these lines from GitHub when you open them, using your own access, and never stores them.">
      <span class="dot-live" aria-hidden="true"></span>Live from GitHub · commit ${esc(b.commit)} · not stored</div>
    <div class="cv-body scroll" tabindex="0" aria-label="Source of ${esc(store.G.name(id))}"><pre class="code">${rows}</pre>${cut}</div>`;
  panel.hidden = false;
  requestAnimationFrame(() => panel.classList.add('on'));
  openId = id;
  opener = from || document.activeElement;
  const def = panel.querySelector('.ln.def');
  if (def) def.scrollIntoView({ block: 'center' });
  panel.querySelector('[data-cv-close]').focus({ preventScroll: true });
}

/** Close the source view and return focus to what opened it. */
export function closeSource(restoreFocus = true) {
  const panel = $('#code');
  if (openId < 0) return;
  openId = -1;
  panel.classList.remove('on');
  setTimeout(() => {
    if (openId < 0) panel.hidden = true;
  }, 200);
  if (restoreFocus && opener && document.contains(opener)) opener.focus({ preventScroll: true });
}

export const sourceOpen = () => openId >= 0;

/** Wire the panel. Called once from main.js. */
export function init() {
  $('#code').addEventListener('click', e => {
    if (e.target.closest('[data-cv-close]')) closeSource();
  });
  $('#code').addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      closeSource();
    }
  });
}
