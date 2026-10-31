/**
 * Uniform-grid collision index for screen-space rectangles (labels, chips). Pure: no DOM.
 * `fits` answers "does this box overlap anything placed so far?" and, if not (or if forced), places it.
 */
export class CollisionGrid {
  /** @param {number} [cell=64] bucket size in px */
  constructor(cell = 64) {
    this.cell = cell;
    this.cols = 0;
    this.rows = 0;
    this.buckets = [];
    this.rects = [];
  }
  /** Clear for a new frame of the given size. */
  reset(width, height) {
    this.cols = Math.ceil(width / this.cell) + 1;
    this.rows = Math.ceil(height / this.cell) + 1;
    const n = this.cols * this.rows;
    if (this.buckets.length !== n) this.buckets = Array.from({ length: n }, () => []);
    else for (const b of this.buckets) b.length = 0;
    this.rects.length = 0;
  }
  range(x0, y0, x1, y1) {
    const c = this.cell,
      cl = (v, hi) => (v < 0 ? 0 : v > hi ? hi : v);
    return [
      cl(Math.floor(x0 / c), this.cols - 1),
      cl(Math.floor(y0 / c), this.rows - 1),
      cl(Math.floor(x1 / c), this.cols - 1),
      cl(Math.floor(y1 / c), this.rows - 1),
    ];
  }
  /**
   * @param {boolean} [force] place even if it overlaps (pinned labels, chips)
   * @returns {boolean} whether the box was placed
   */
  fits(x0, y0, x1, y1, force = false) {
    const [a, b, c, d] = this.range(x0, y0, x1, y1),
      R = this.rects;
    if (!force)
      for (let y = b; y <= d; y++)
        for (let x = a; x <= c; x++)
          for (const r of this.buckets[y * this.cols + x]) {
            if (x0 < R[r + 2] && x1 > R[r] && y0 < R[r + 3] && y1 > R[r + 1]) return false;
          }
    const id = R.length;
    R.push(x0, y0, x1, y1);
    for (let y = b; y <= d; y++) for (let x = a; x <= c; x++) this.buckets[y * this.cols + x].push(id);
    return true;
  }
}
