/**
 * Key panel: the links between services by how they are proven (as the map draws them) and by protocol, contract
 * line styles, node shapes and the active colour mode. Folds away while a side panel is open. Its sections sit behind
 * a segmented control (after 21st.dev segmented controls), one at a time, so the Key stays short on any screen.
 */
import { stOn, store } from '../state.js';
import { flyToTerr } from '../app/camera.js';
import { deselect } from '../app/selection.js';
import { HTTP_ARC } from '../config.js';
import { LEGB } from '../dom.js';
import { isWithin, PROOF, PROOF_ORDER, proofCounts, protocolCounts, protocolName } from '../model/http.js';
import { KIND, STATUS } from '../model/vocab.js';
import { arcStyle } from '../render/http.js';
import { requestRender } from '../render/frame.js';
import { bundleStyle } from '../render/scene.js';
import { css, theme } from '../render/theme.js';
import { setGroup, syncThumb } from './controls.js';
import { nameAttrs } from './fragments.js';
import { esc, fmt } from '../util/format.js';

const keyRow = (swatch, label, n) =>
  `<div class="lg-row lg-static">${swatch}<span>${esc(label)}</span><span class="n">${fmt(n)}</span></div>`;

/** The links between services, one row per proof in the line style the map draws, then their protocols. */
function linksGroup(H) {
  if (!H || !(H.links.length || H.unmatched.length)) return '';
  const c = proofCounts(H),
    within = H.links.filter(isWithin).length;
  let h = `<div class="lg-group"><div class="lg-h">Links between services</div>`;
  for (const p of PROOF_ORDER) {
    if (!c[p]) continue;
    const [col, dash] = arcStyle(p);
    // dotted (Jev, outside), dash-dot (read by AI) or dashed, as on the map
    const style = !dash ? '' : dash.length > 2 ? ' dashdot' : dash[0] <= 2 ? ' dot' : ' dash';
    h += keyRow(`<span class="sw-line${style}" style="--c:${css(col)}"></span>`, PROOF[p].label, c[p]);
  }
  if (within) {
    const col = css(theme.text, Math.max(HTTP_ARC.withinAlpha, 0.45)); // drawn fainter on the map, by its proof
    h += keyRow(`<span class="sw-line" style="--c:${col}"></span>`, 'Inside one repository', within);
  }
  if (H.unmatched.length)
    h += keyRow(`<span class="sw-dot" style="--c:${css(theme.st[2])}"></span>`, 'No route found', H.unmatched.length);
  const protocols = protocolCounts(H)
    .map(([p, n]) => `${esc(protocolName(p))} ${fmt(n)}`)
    .join(' · ');
  return h + `<div class="lg-note">${protocols}</div></div>`;
}

let tab = '', // the section shown; kept across re-renders of one map's Key
  shape = ''; // the sections a map has: when they change (another map), the Key starts on the first

/** The section switcher and the sections it shows, one visible at a time. */
function sections(parts) {
  const now = parts.map(p => p.v).join();
  if (now !== shape || !parts.some(p => p.v === tab)) tab = parts[0].v;
  shape = now;
  const radios = parts
    .map(p => `<button type="button" role="radio" data-v="${p.v}" aria-checked="false">${esc(p.label)}</button>`)
    .join('');
  const panes = parts.map(
    p => `<div class="lg-pane" data-pane="${p.v}"${p.v === tab ? '' : ' hidden'}>${p.html}</div>`,
  );
  return `<div class="toggle-group lg-tabs" role="radiogroup" aria-label="Key section"><span class="thumb"></span>${radios}</div><div class="lg-panes">${panes.join('')}</div>`;
}

/** Show section `v` without rebuilding the Key, so focus stays on the switcher. */
function showSection(v) {
  tab = v;
  LEGB.querySelectorAll('.lg-pane').forEach(p => (p.hidden = p.dataset.pane !== v));
  setGroup(LEGB.querySelector('.lg-tabs'), v);
}

export function renderLegend() {
  const g = store.G,
    H = g.http,
    channels = !!H && H.links.some(l => l.protocol && l.protocol !== 'http');
  const links = linksGroup(H),
    code = H && H.links.length;
  let h = `<div class="lg-group"><div class="lg-h">${code ? 'Code graph' : 'Contracts'}</div>`;
  STATUS.forEach((s, i) => {
    const col = i === 0 ? css(theme.text, 0.55) : css(theme.st[i]);
    h += `<button class="lg-row" data-st="${i}" aria-pressed="${!!stOn[i] && (!store.issuesOnly || i === 1 || i === 2)}"><span class="sw-line${i === 3 ? ' dash' : ''}" style="--c:${col}"></span><span>${s}</span><span class="n">${fmt(g.BYST[i])}</span></button>`;
  });
  if (g.SCIPN)
    // of the edges above, those a SCIP index (a compiler-grade view of the code) shows
    h += keyRow(`<span class="sw-dot" style="--c:${css(theme.proof)}"></span>`, 'Seen by SCIP', g.SCIPN);
  const codeHtml = h + '</div>';
  h = `<div class="lg-group">`;
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
  const parts = [
    ...(links ? [{ v: 'links', label: 'Links', html: links }] : []),
    { v: 'code', label: code ? 'Code' : 'Contracts', html: codeHtml },
    { v: 'repos', label: store.colorMode === 'health' ? 'Health' : 'Repos', html: h + '</div>' },
  ];
  h =
    sections(parts) +
    `<div class="lg-group lg-foot"><div class="shapes"><span><i class="g ep"></i>${KIND[1]}</span><span><i class="g ev"></i>${channels ? 'Endpoint or topic' : KIND[2]}</span><span><i class="g md"></i>${KIND[3]}</span></div></div>`;
  if (g.meta && g.meta.source)
    h += `<div class="lg-group"><div class="lg-h">Indexed with ${esc(g.meta.source)}</div></div>`;
  LEGB.innerHTML = h;
  setGroup(LEGB.querySelector('.lg-tabs'), tab);
}

/** The switcher's thumb needs the Key open to measure; call when it opens. */
export function syncLegend() {
  const el = LEGB.querySelector('.lg-tabs');
  if (el) syncThumb(el); // the page's first toggle event comes before the Key is drawn
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  LEGB.parentElement.addEventListener('toggle', syncLegend); // the thumb can only be measured while the Key is open
  LEGB.addEventListener('keydown', e => {
    const bs = [...LEGB.querySelectorAll('.lg-tabs [role="radio"]')],
      i = bs.indexOf(document.activeElement),
      step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (i < 0 || !step) return;
    e.preventDefault();
    const b = bs[(i + step + bs.length) % bs.length];
    showSection(b.dataset.v);
    b.focus();
  });
  LEGB.addEventListener('click', e => {
    const r = e.target.closest('.lg-tabs [role="radio"]');
    if (r) return showSection(r.dataset.v);
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
