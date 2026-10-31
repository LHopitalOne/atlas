import { test } from 'node:test';
import assert from 'node:assert/strict';
import { convexHull, hullTop, median, angDiff } from '../src/model/geometry.js';

test('convex hull drops interior points', () => {
  const h = convexHull([
    [0, 0],
    [10, 0],
    [10, 10],
    [0, 10],
    [5, 5],
    [3, 7],
  ]);
  assert.equal(h.length / 2, 4);
  assert.equal(hullTop(h), 0);
});
test('median and angle difference', () => {
  assert.equal(median([5, 1, 3]), 3);
  assert.ok(Math.abs(angDiff(Math.PI - 0.1, -Math.PI + 0.1) - 0.2) < 1e-9);
});
