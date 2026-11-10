/**
 * Theme: reads the CSS colour tokens (OKLCH) into linear RGB for the GPU, and colour helpers for nodes and bundles.
 */
import { store } from '../state.js';
import { clamp, sstep } from '../util/math.js';

export const theme = {};
function parseCol(s) {
  s = s.trim();
  if (s[0] === '#') {
    let h = s.slice(1);
    if (h.length === 3)
      h = h
        .split('')
        .map(c => c + c)
        .join('');
    const n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const m = s.match(/[\d.]+/g).map(Number);
  return [m[0], m[1], m[2], m[3] === undefined ? 1 : m[3]];
}
export const mixc = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
export const css = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
export function readTheme() {
  const cs = getComputedStyle(document.documentElement),
    g = n => parseCol(cs.getPropertyValue(n));
  Object.assign(theme, {
    bg: g('--map'),
    text: g('--foreground'),
    muted: g('--muted-foreground'),
    faint: g('--faint'),
    halo: g('--halo'),
    edge: g('--edge'),
    grid: g('--grid'),
    route: g('--route'),
    proof: g('--proof'),
    node: g('--node'),
    other: g('--other'),
  });
  theme.pal = [g('--r0'), g('--r1'), g('--r2'), g('--r3'), g('--r4')];
  theme.st = [g('--node'), g('--warning'), g('--destructive'), g('--inferred')];
  theme.dark = theme.bg[0] * 0.299 + theme.bg[1] * 0.587 + theme.bg[2] * 0.114 < 128;
}
// Only the five largest repositories get a hue; everything else stays neutral so colour keeps meaning
const repoCol = r => (store.repoRank[r] < 5 ? theme.pal[store.repoRank[r]] : theme.other);
// typical services stay neutral; colour starts only when a service is clearly worse than average
const healthCol = h =>
  h < 0.3 ? mixc(theme.node, theme.st[1], sstep(h, 0.15, 0.3)) : mixc(theme.st[1], theme.st[2], sstep(h, 0.3, 0.55));
export const put4 = (arr, i, c, a) => {
  arr[i * 4] = c[0];
  arr[i * 4 + 1] = c[1];
  arr[i * 4 + 2] = c[2];
  arr[i * 4 + 3] = Math.round(clamp(a, 0, 1) * 255);
};
export const nodeCol = i => {
  const g = store.G;
  if (store.colorMode === 'repo') return repoCol(g.domRepo[g.svcDom[g.own(i)]]);
  if (i < g.S) {
    const m = g.SVST[i * 4],
      a = g.SVST[i * 4 + 1],
      u = g.SVST[i * 4 + 2],
      t = m + a + u;
    return healthCol(t ? (a * 0.5 + u) / t : 0);
  }
  return g.ISS[i] === 2 ? theme.st[2] : g.ISS[i] === 1 ? theme.st[1] : theme.faint;
};
