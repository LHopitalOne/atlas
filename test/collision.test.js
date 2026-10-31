import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CollisionGrid } from '../src/render/collision.js';

test('places non-overlapping boxes, rejects overlaps', () => {
  const c = new CollisionGrid(64);
  c.reset(500, 300);
  assert.ok(c.fits(10, 10, 60, 30));
  assert.ok(!c.fits(50, 20, 120, 40));
  assert.ok(c.fits(70, 10, 120, 30));
});
test('forced boxes are placed and then block others', () => {
  const c = new CollisionGrid(64);
  c.reset(500, 300);
  assert.ok(c.fits(100, 100, 200, 120, true));
  assert.ok(c.fits(100, 100, 200, 120, true), 'forced even when overlapping');
  assert.ok(!c.fits(150, 110, 160, 115));
});
test('boxes spanning many buckets and off-screen boxes', () => {
  const c = new CollisionGrid(32);
  c.reset(200, 200);
  assert.ok(c.fits(-50, -50, 250, 10));
  assert.ok(!c.fits(190, 0, 199, 5));
  c.reset(200, 200);
  assert.ok(c.fits(190, 0, 199, 5), 'reset clears');
});
