/** Small pure geometry helpers used by the layout. */

/**
 * Convex hull (monotone chain) of [x, y] points.
 * @param {Array<[number, number]>} pts sorted in place
 * @returns {Float32Array} hull as a flat [x0, y0, x1, y1, ...] array, counter-clockwise
 */
export function convexHull(pts) {
  pts.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [],
    up = [];
  for (const p of pts) {
    while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop();
    lo.push(p);
  }
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop();
    up.push(p);
  }
  up.pop();
  lo.pop();
  const h = lo.concat(up),
    f = new Float32Array(h.length * 2);
  h.forEach((p, i) => {
    f[i * 2] = p[0];
    f[i * 2 + 1] = p[1];
  });
  return f;
}

/** Smallest y of a flat hull. */
export function hullTop(h) {
  let m = 1e9;
  for (let i = 1; i < h.length; i += 2) if (h[i] < m) m = h[i];
  return m;
}

/** Median of a numeric array (upper median for even lengths). */
export function median(a) {
  const b = Float64Array.from(a).sort();
  return b[b.length >> 1];
}

/** Absolute angular difference in radians, in [0, π]. */
export const angDiff = (a, b) => Math.abs(Math.atan2(Math.sin(a - b), Math.cos(a - b)));
