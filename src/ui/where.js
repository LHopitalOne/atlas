/**
 * Location breadcrumb: which repository and domain the view centre is over, and the level the labels show.
 */
import { cam, store } from '../state.js';
import { viewCenter } from '../app/camera.js';
import { WHERE } from '../dom.js';
import { onFrameDrawn } from '../render/frame.js';
import { nameAttrs } from './fragments.js';
import { esc } from '../util/format.js';

export function levelOf(V) {
  const k = cam.k,
    g = store.G;
  return k >= 2.1
    ? 'Endpoints'
    : V.svcA > 0.4 && g.medRF * k >= 13
      ? 'Services'
      : V.aDL > 0.5
        ? 'Domains'
        : 'Repositories';
}
export function updateWhere(V) {
  const g = store.G,
    c = viewCenter(),
    wx = (c.x - cam.x) / cam.k,
    wy = (c.y - cam.y) / cam.k;
  let r = -1,
    d = -1;
  for (let i = 0; i < g.R; i++)
    if (Math.hypot(wx - g.rx[i], wy - g.ry[i]) < g.rR[i]) {
      r = i;
      break;
    }
  if (r >= 0)
    for (let j = g.rDs[r]; j < g.rDe[r]; j++)
      if (Math.hypot(wx - g.dcx[j], wy - g.dcy[j]) < g.dR[j]) {
        d = j;
        break;
      }
  const lvl = levelOf(V),
    key = lvl + r + '|' + d;
  if (key === store.whereKey) return;
  store.whereKey = key;
  WHERE.innerHTML = `<span class="badge badge-secondary">${lvl}</span><span class="loc" ${nameAttrs}>${r < 0 ? 'Between repositories' : esc(g.repoName[r]) + (d >= 0 ? `<span aria-hidden="true">/</span>${esc(g.domName[d])}` : '')}</span>`;
}

/** Subscribe the breadcrumb to the frame loop. Called once from main.js. */
export function init() {
  onFrameDrawn(updateWhere);
}
