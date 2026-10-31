/** Pure numeric helpers: clamping, smoothing and easing curves. Safe in Node and the browser. */
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const sstep = (x, a, b) => {
  const t = clamp((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
export const ease = p => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
export function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1,
    bx = 3 * (x2 - x1) - cx,
    ax = 1 - cx - bx,
    cy = 3 * y1,
    by = 3 * (y2 - y1) - cy,
    ay = 1 - cy - by;
  const X = t => ((ax * t + bx) * t + cx) * t,
    Y = t => ((ay * t + by) * t + cy) * t,
    dX = t => (3 * ax * t + 2 * bx) * t + cx;
  return x => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) {
      const d = dX(t);
      if (Math.abs(d) < 1e-6) break;
      t -= (X(t) - x) / d;
      t = clamp(t, 0, 1);
    }
    return Y(t);
  };
}
export const easeMove = cubicBezier(0.77, 0, 0.175, 1);
export const easeOut = cubicBezier(0.23, 1, 0.32, 1);
