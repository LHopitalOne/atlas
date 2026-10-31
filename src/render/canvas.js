/** Shared 2D-canvas helpers for the overlay layer. */
import { oc } from '../dom.js';
import { css, theme } from './theme.js';
import { CollisionGrid } from './collision.js';

/** Text-width cache (font|text -> px). Cleared when fonts finish loading. */
export const measure = new Map();
/** One collision grid per frame, shared by edge chips and labels. */
export const LC = new CollisionGrid(64);

/** Measured width of `text` in `font`, cached. */
export const tw = (font, str) => {
  const key = font + '|' + str;
  let w = measure.get(key);
  if (w === undefined) {
    oc.font = font;
    w = oc.measureText(str).width;
    measure.set(key, w);
  }
  return w;
};

/** Text with a halo in the map background colour, so it stays legible over lines. */
export function text(t, x, y, align, font, color, alpha, halo = 3.4) {
  oc.font = font;
  oc.textAlign = align;
  oc.globalAlpha = alpha;
  oc.lineWidth = halo;
  oc.strokeStyle = css(theme.halo);
  oc.strokeText(t, x, y);
  oc.fillStyle = color;
  oc.fillText(t, x, y);
}

/** Rounded-rectangle path. */
export function rrect(x, y, w, h, r) {
  oc.beginPath();
  oc.moveTo(x + r, y);
  oc.arcTo(x + w, y, x + w, y + h, r);
  oc.arcTo(x + w, y + h, x, y + h, r);
  oc.arcTo(x, y + h, x, y, r);
  oc.arcTo(x, y, x + w, y, r);
  oc.closePath();
}
