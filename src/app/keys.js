/**
 * Global keyboard shortcuts: / or Cmd/Ctrl+K search, F fit, I issues, D directions, C colour mode, +/- zoom, arrows pan.
 */
import { route, store } from '../state.js';
import { fitAll, inspOpen, viewCenter, zoomAt } from './camera.js';
import { keyHover, panBy } from './pointer.js';
import { deselect } from './selection.js';
import { ov, Q } from '../dom.js';
import { renderAttn } from '../ui/attention.js';
import { setMode, toggleIssues } from '../ui/controls.js';
import { renderRoute, startDirections } from '../ui/directions.js';
import { closeSource, sourceOpen } from '../ui/code-view.js';
import { askOpen, closeAsk, openAsk } from '../ui/ask.js';
import { closeLinksPanel, toggleLinksPanel } from '../ui/links.js';

const zoomStep = f => {
  const c = viewCenter();
  zoomAt(c.x, c.y, f);
  if (store.kbdMap) keyHover();
};
function escape() {
  if (sourceOpen()) closeSource();
  else if (route.picking) {
    route.picking = null;
    renderRoute();
  } else if (inspOpen()) deselect(true);
  else if (store.attnOpen) {
    store.attnOpen = false;
    renderAttn();
  } else if (askOpen()) closeAsk();
  else if (store.linksOpen && store.G && store.G.http) closeLinksPanel();
}
/** Single-key shortcuts (ignored while typing). */
const SHORTCUTS = {
  escape,
  f: () => fitAll(),
  i: () => toggleIssues(),
  d: () => startDirections(),
  a: () => openAsk(),
  l: () => store.G && store.G.http && toggleLinksPanel(),
  c: () => {
    store.userColor = true;
    setMode(store.colorMode === 'health' ? 'repo' : 'health');
  },
  '=': () => zoomStep(1.4),
  '+': () => zoomStep(1.4),
  '-': () => zoomStep(1 / 1.4),
};
const ARROWS = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
const isTyping = el => el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA';

function onKey(e) {
  if (!store.G || isTyping(e.target)) return;
  if (e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) {
    e.preventDefault();
    Q.focus();
    return;
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const onMap = e.target === ov || e.target === document.body;
  if (onMap && ARROWS[e.key]) {
    e.preventDefault();
    const step = e.shiftKey ? 240 : 80,
      [dx, dy] = ARROWS[e.key];
    panBy(dx * step, dy * step);
    return;
  }
  const action = SHORTCUTS[e.key.toLowerCase()];
  if (!action) return;
  e.preventDefault(); // a shortcut that focuses a text box must not also type its key into it
  action();
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  document.addEventListener(
    'keydown',
    () => {
      store.viaKeys = true;
    },
    true,
  );
  document.addEventListener(
    'pointerdown',
    () => {
      store.viaKeys = false;
    },
    true,
  );
  document.addEventListener('keydown', onKey);
}
