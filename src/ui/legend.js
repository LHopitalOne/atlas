/**
 * Key panel: contract line styles, node shapes and the active colour mode. Folds away while a side panel is open.
 */
import { stOn, store } from '../state.js';
import { flyToTerr } from '../app/camera.js';
import { deselect } from '../app/selection.js';
import { LEGB } from '../dom.js';
import { KIND, STATUS } from '../model/vocab.js';
import { requestRender } from '../render/frame.js';
import { bundleStyle } from '../render/scene.js';
import { css, theme } from '../render/theme.js';
import { nameAttrs } from './fragments.js';
import { esc, fmt } from '../util/format.js';

export function renderLegend() {
  const g = store.G;
  let h = `<div class="lg-group"><div class="lg-h">Contracts</div>`;
  STATUS.forEach((s, i) => {
    const col = i === 0 ? css(theme.text, 0.55) : css(theme.st[i]);
    h += `<button class="lg-row" data-st="${i}" aria-pressed="${!!stOn[i] && (!store.issuesOnly || i === 1 || i === 2)}"><span class="sw-line${i === 3 ? ' dash' : ''}" style="--c:${col}"></span><span>${s}</span><span class="n">${fmt(g.BYST[i])}</span></button>`;
  });
  h += `</div><div class="lg-group">`;
  if (store.colorMode === 'health')
    h += `<div class="lg-h">Service health</div><div class="hgrad"></div><div class="hgrad-l"><span>Clean</span><span>Mostly broken</span></div>`;
  else {
    h += `<div class="lg-h">Repositories</div>`;
    const top = [...g.repoOrder].filter(r => store.repoRank[r] < 5);
    for (const r of top)
      h += `<button class="lg-row" data-repo="${r}"><span class="sw-dot" style="--c:${css(theme.pal[store.repoRank[r]])}"></span><span class="nm" ${nameAttrs}>${esc(g.repoName[r])}</span><span class="n">${fmt(g.rDe[r] - g.rDs[r])} dom.</span></button>`;
    if (g.R > 5)
      h += `<div class="lg-row" style="cursor:default"><span class="sw-dot" style="--c:${css(theme.other)}"></span><span>${fmt(g.R - 5)} other ${g.R - 5 === 1 ? 'repository' : 'repositories'}</span><span></span></div>`;
  }
  h += `</div><div class="lg-group"><div class="shapes"><span><i class="g ep"></i>${KIND[1]}</span><span><i class="g ev"></i>${KIND[2]}</span><span><i class="g md"></i>${KIND[3]}</span></div></div>`;
  if (g.meta && g.meta.source)
    h += `<div class="lg-group"><div class="lg-h">Indexed with ${esc(g.meta.source)}</div></div>`;
  LEGB.innerHTML = h;
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  LEGB.addEventListener('click', e => {
    const b = e.target.closest('.lg-row');
    if (!b) return;
    if (b.dataset.repo) {
      deselect();
      flyToTerr('r', +b.dataset.repo);
      return;
    }
    if (b.dataset.st === undefined) return;
    stOn[+b.dataset.st] ^= 1;
    bundleStyle();
    renderLegend();
    requestRender();
  });
}
