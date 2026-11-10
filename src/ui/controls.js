/**
 * Toolbar and dock controls: scale and colour segmented controls, Issues toggle, fit, directions, dock tooltips.
 */
import { store } from '../state.js';
import { fitAll } from '../app/camera.js';
import { loadDataset } from '../app/dataset.js';
import { writeHash } from '../app/url.js';
import { DOCK, TIP } from '../dom.js';
import { requestRender } from '../render/frame.js';
import { bundleStyle, recolor } from '../render/scene.js';
import { renderAttn } from './attention.js';
import { startDirections } from './directions.js';
import { announce } from './feedback.js';
import { openInspector } from './inspector.js';
import { renderLegend } from './legend.js';
import { $ } from '../util/dom.js';
import { esc } from '../util/format.js';
import { mapList } from '../model/maps.js';

/** A dataset button's value: a synthetic size is a number; Self and map keys stay strings. */
const datasetOf = v => (/^\d+$/.test(v) ? +v : v);

/** Builds with embedded maps offer those maps, and only those, in the dataset control. */
function mapButtons() {
  const maps = mapList();
  if (!maps.length) return;
  const group = $('#scale'),
    sel = $('#scaleSel');
  group.setAttribute('aria-label', 'Map');
  sel.setAttribute('aria-label', 'Map');
  group.innerHTML =
    '<span class="thumb" aria-hidden="true"></span>' +
    maps
      .map(
        (m, i) =>
          `<button role="radio" data-v="${esc(m.key)}" aria-checked="${i === 0}" tabindex="${i === 0 ? 0 : -1}">${esc(m.label)}</button>`,
      )
      .join('');
  sel.innerHTML = maps.map(m => `<option value="${esc(m.key)}">${esc(m.label)}</option>`).join('');
}

/* segmented controls: radiogroups with a sliding thumb and arrow-key navigation */
export function syncThumb(el) {
  const b = el.querySelector('[aria-checked="true"]'),
    t = el.querySelector('.thumb');
  if (!b || !t || !b.offsetWidth) return;
  t.style.width = b.offsetWidth + 'px';
  t.style.transform = `translateX(${b.offsetLeft}px)`;
}
export function setGroup(el, v) {
  el.querySelectorAll('[role="radio"]').forEach(b => {
    const on = b.dataset.v === String(v);
    b.setAttribute('aria-checked', on);
    b.tabIndex = on ? 0 : -1;
  });
  syncThumb(el);
}
function radioGroup(el, onPick) {
  el.addEventListener('click', e => {
    const b = e.target.closest('[role="radio"]');
    if (b && b.getAttribute('aria-checked') !== 'true') onPick(b.dataset.v);
  });
  el.addEventListener('keydown', e => {
    const bs = [...el.querySelectorAll('[role="radio"]')],
      i = bs.indexOf(document.activeElement);
    if (i < 0) return;
    const j =
      e.key === 'ArrowRight' || e.key === 'ArrowDown'
        ? (i + 1) % bs.length
        : e.key === 'ArrowLeft' || e.key === 'ArrowUp'
          ? (i - 1 + bs.length) % bs.length
          : e.key === 'Home'
            ? 0
            : e.key === 'End'
              ? bs.length - 1
              : -1;
    if (j < 0) return;
    e.preventDefault();
    e.stopPropagation();
    bs[j].focus();
    onPick(bs[j].dataset.v);
  });
}
export function setMode(m) {
  store.colorMode = m;
  store.placeDirty = true;
  setGroup($('#seg'), m);
  recolor();
  renderLegend();
  if (store.selectedId >= 0) openInspector(store.selectedId);
  writeHash();
}
export function toggleIssues(force) {
  if (!store.G) return;
  store.issuesOnly = force === undefined ? !store.issuesOnly : force;
  $('#issues').setAttribute('aria-pressed', store.issuesOnly);
  store.attnOpen = store.issuesOnly;
  store.placeDirty = true;
  bundleStyle();
  renderLegend();
  renderAttn();
  requestRender();
  writeHash();
  if (force === undefined)
    announce(store.issuesOnly ? 'Showing only ambiguous and unmatched contracts.' : 'Showing all contracts.');
}
// first tooltip waits a beat; once one is open, neighbours appear instantly with no animation
let tipTO = 0;
function placeTip(b) {
  TIP.innerHTML = esc(b.dataset.tip) + (b.dataset.kbd ? `<span class="kbd">${b.dataset.kbd}</span>` : '');
  const x = Math.min(b.offsetLeft + b.offsetWidth / 2 - TIP.offsetWidth / 2, DOCK.offsetWidth - TIP.offsetWidth);
  TIP.style.transform = `translateX(${x}px)`;
}
function showTip(b) {
  clearTimeout(tipTO);
  if (!b || !b.dataset.tip) {
    TIP.classList.remove('on', 'instant');
    return;
  }
  if (TIP.classList.contains('on')) {
    TIP.classList.add('instant');
    placeTip(b);
    return;
  }
  tipTO = setTimeout(() => {
    TIP.classList.remove('instant');
    placeTip(b);
    TIP.classList.add('on');
  }, 350);
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  radioGroup($('#seg'), v => {
    store.userColor = true;
    setMode(v);
  });
  mapButtons();
  radioGroup($('#scale'), v => loadDataset(datasetOf(v)));
  $('#issues').addEventListener('click', () => toggleIssues());
  $('#fit').addEventListener('click', () => fitAll());
  $('#dirBtn').addEventListener('click', () => startDirections());
  DOCK.addEventListener('pointerover', e => showTip(e.target.closest('button')));
  DOCK.addEventListener('pointerleave', () => showTip(null));
  DOCK.addEventListener('focusin', e => showTip(e.target.closest('button')));
  DOCK.addEventListener('focusout', () => showTip(null));
  $('#scaleSel').addEventListener('change', e => loadDataset(datasetOf(e.target.value)));
}
