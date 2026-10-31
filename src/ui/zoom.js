/**
 * Zoom slider: log scale between the dataset's zoom limits; follows every other way of zooming.
 */
import { cam, store } from '../state.js';
import { viewCenter, zoomAt } from '../app/camera.js';
import { ZS } from '../dom.js';
import { onFrameDrawn } from '../render/frame.js';
import { levelOf } from './where.js';
import { clamp } from '../util/math.js';

let zDrag = false;
const k2s = k =>
  Math.round(1000 * clamp((Math.log(k) - Math.log(store.KMIN)) / (Math.log(store.KMAX) - Math.log(store.KMIN)), 0, 1));
const s2k = v => Math.exp(Math.log(store.KMIN) + ((Math.log(store.KMAX) - Math.log(store.KMIN)) * v) / 1000);
let zLevel = '';
export function syncZoom(V) {
  if (!zDrag) {
    const v = k2s(cam.k);
    if (+ZS.value !== v) ZS.value = v;
  }
  ZS.style.setProperty('--p', +ZS.value / 10 + '%');
  const lvl = levelOf(V);
  if (lvl !== zLevel) {
    zLevel = lvl;
    ZS.setAttribute('aria-valuetext', `${lvl} level`);
  }
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  onFrameDrawn(syncZoom);
  ZS.addEventListener('input', () => {
    if (!store.G) return;
    const c = viewCenter();
    zoomAt(c.x, c.y, s2k(+ZS.value) / cam.k);
  });
  ZS.addEventListener('pointerdown', () => {
    zDrag = true;
  });
  window.addEventListener('pointerup', () => {
    zDrag = false;
  });
}
