/**
 * Overview map: territory silhouettes, a clipped viewport box, click or drag to move there.
 */
import { cam, store } from '../state.js';
import { fitAll, viewCenter } from '../app/camera.js';
import { requestRender } from './frame.js';
import { css, theme } from './theme.js';
import { $ } from '../util/dom.js';
import { clamp } from '../util/math.js';

const mm = $('#mm');
const mctx = mm.getContext('2d');
let mmBase = null;
let MT = { s: 1, ox: 0, oy: 0, md: 1 };
export function buildMinimap() {
  if (!store.G) return;
  const g = store.G,
    md = Math.max(1, devicePixelRatio || 1),
    w = 196,
    h = 128,
    pad = 10;
  // bounds of what is actually drawn (the territory outlines), so the overview is truly centred
  let x0 = 1e9,
    y0 = 1e9,
    x1 = -1e9,
    y1 = -1e9;
  for (const hh of g.rHull)
    for (let i = 0; i < hh.length; i += 2) {
      x0 = Math.min(x0, hh[i]);
      x1 = Math.max(x1, hh[i]);
      y0 = Math.min(y0, hh[i + 1]);
      y1 = Math.max(y1, hh[i + 1]);
    }
  mm.width = w * md;
  mm.height = h * md;
  const s = Math.min((w - pad * 2) / (x1 - x0), (h - pad * 2) / (y1 - y0));
  MT = { s, ox: (w - (x1 - x0) * s) / 2 - x0 * s, oy: (h - (y1 - y0) * s) / 2 - y0 * s, md, w, h };
  mmBase = document.createElement('canvas');
  mmBase.width = w * md;
  mmBase.height = h * md;
  const c2 = mmBase.getContext('2d');
  c2.setTransform(md * s, 0, 0, md * s, md * MT.ox, md * MT.oy);
  for (let r = 0; r < g.R; r++) {
    const hh = g.rHull[r];
    c2.beginPath();
    for (let i = 0; i < hh.length; i += 2) c2.lineTo(hh[i], hh[i + 1]);
    c2.closePath();
    const top = store.colorMode === 'repo' && store.repoRank[r] < 5;
    c2.fillStyle = top ? css(theme.pal[store.repoRank[r]], 0.5) : css(theme.text, 0.13);
    c2.fill();
  }
}
export function drawMinimap() {
  if (!mmBase || store.W <= 760) return;
  const md = MT.md,
    mw = MT.w,
    mh = MT.h;
  mctx.setTransform(1, 0, 0, 1, 0, 0);
  mctx.clearRect(0, 0, mm.width, mm.height);
  mctx.drawImage(mmBase, 0, 0);
  mctx.setTransform(md, 0, 0, md, 0, 0);
  const vx0 = (-cam.x / cam.k) * MT.s + MT.ox,
    vy0 = (-cam.y / cam.k) * MT.s + MT.oy,
    vx1 = vx0 + (store.W / cam.k) * MT.s,
    vy1 = vy0 + (store.H / cam.k) * MT.s;
  const cx0 = clamp(vx0, 0.5, mw - 0.5),
    cy0 = clamp(vy0, 0.5, mh - 0.5),
    cx1 = clamp(vx1, 0.5, mw - 0.5),
    cy1 = clamp(vy1, 0.5, mh - 0.5);
  if (cx1 - cx0 > 1 && cy1 - cy0 > 1) {
    mctx.fillStyle = css(theme.text, 0.06);
    mctx.fillRect(cx0, cy0, cx1 - cx0, cy1 - cy0);
    mctx.strokeStyle = css(theme.text, 0.7);
    mctx.lineWidth = 1;
    mctx.strokeRect(cx0, cy0, cx1 - cx0, cy1 - cy0);
  } else {
    // looking entirely outside the overview: a small arrow on the edge points to where the view is
    const tx = (vx0 + vx1) / 2,
      ty = (vy0 + vy1) / 2,
      ex = clamp(tx, 7, mw - 7),
      ey = clamp(ty, 7, mh - 7),
      a = Math.atan2(ty - mh / 2, tx - mw / 2);
    mctx.save();
    mctx.translate(ex, ey);
    mctx.rotate(a);
    mctx.beginPath();
    mctx.moveTo(5, 0);
    mctx.lineTo(-3, -4);
    mctx.lineTo(-3, 4);
    mctx.closePath();
    mctx.fillStyle = css(theme.text, 0.8);
    mctx.fill();
    mctx.restore();
  }
}
let mmDrag = false;
const mmGo = e => {
  const wx = (e.offsetX - MT.ox) / MT.s,
    wy = (e.offsetY - MT.oy) / MT.s,
    c = viewCenter();
  store.anim = null;
  cam.x = c.x - wx * cam.k;
  cam.y = c.y - wy * cam.k;
  requestRender();
};

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  mm.addEventListener('pointerdown', e => {
    mmDrag = true;
    mm.setPointerCapture(e.pointerId);
    mmGo(e);
  });
  mm.addEventListener('pointermove', e => {
    if (mmDrag) mmGo(e);
  });
  mm.addEventListener('pointerup', () => (mmDrag = false));
  mm.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fitAll();
    }
  });
}
