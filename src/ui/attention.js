/**
 * Needs attention panel: the services with the most ambiguous or unmatched contracts, shown when Issues is on.
 */
import { store } from '../state.js';
import { select } from '../app/selection.js';
import { ATTN, RT } from '../dom.js';
import { STATUS } from '../model/vocab.js';
import { dotHTML, ICON_X, nameAttrs, pills } from './fragments.js';
import { $ } from '../util/dom.js';
import { esc } from '../util/format.js';
import { closeAsk } from './ask.js';

let attnList = [];
export function buildAttn() {
  const g = store.G,
    a = [];
  for (let s = 0; s < g.S; s++) {
    const u = g.SVST[s * 4 + 2],
      m = g.SVST[s * 4 + 1];
    if (u + m) a.push([u * 2 + m, s]);
  }
  a.sort((x, y) => y[0] - x[0]);
  attnList = a.slice(0, 25).map(x => x[1]);
}
// a left panel and the open Key would overlap: fold the Key while a panel is open, restore it after
let leftWas = false;
let legendWas = true;
/** Fold the Key while a left panel is open; restore it afterwards. */
export function syncLegend() {
  const L = $('#legend'),
    now = RT.classList.contains('on') || ATTN.classList.contains('on');
  if (now && !leftWas) {
    legendWas = L.open;
    L.open = false;
  } else if (!now && leftWas) {
    L.open = legendWas;
  }
  leftWas = now;
}
export function renderAttn() {
  if (store.attnOpen) closeAsk();
  const g = store.G;
  const show = store.attnOpen && !RT.classList.contains('on');
  ATTN.classList.toggle('on', show);
  syncLegend();
  if (!show) {
    return;
  }
  let h = `<div class="ph"><div><h2 id="attnTitle">Needs attention</h2><p>Services with the most ${STATUS[2].toLowerCase()} and ${STATUS[1].toLowerCase()} links</p></div><button class="btn btn-ghost btn-icon" data-aclose aria-label="Close list">${ICON_X}</button></div><div class="scroll" style="padding:0 8px 10px">`;
  for (const s of attnList) {
    const d = g.svcDom[s];
    h += `<button class="row" data-id="${s}">${dotHTML(s)}<span class="rn" ${nameAttrs}>${esc(g.svcName[s])}<span class="rs">${esc(g.repoName[g.domRepo[d]])}, ${esc(g.domName[d])}</span></span><span class="rm">${pills([0, g.SVST[s * 4 + 1], g.SVST[s * 4 + 2], 0])}</span></button>`;
  }
  ATTN.innerHTML = h + `</div>`;
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  ATTN.addEventListener('click', e => {
    if (e.target.closest('[data-aclose]')) {
      store.attnOpen = false;
      renderAttn();
      return;
    }
    const t = e.target.closest('[data-id]');
    if (t) select(+t.dataset.id, 'list');
  });
}
