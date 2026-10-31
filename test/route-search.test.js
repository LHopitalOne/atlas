import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tinyGraph } from './helpers.js';
import { routeSearch, callerCount } from '../src/graph/route-search.js';

test('follows calls forwards', () => {
  const g = tinyGraph();
  const r = routeSearch(g, [0], [2]);
  assert.deepEqual(r.path, [0, 1, 2]);
  assert.deepEqual(
    [...r.path.slice(1)].map(v => r.fwd[v]),
    [1, 1],
  );
});

test('no forward chain, but one exists against a call', () => {
  const g = tinyGraph();
  assert.equal(routeSearch(g, [0], [3]), null);
  const r = routeSearch(g, [0], [3], { either: true });
  assert.deepEqual(r.path, [0, 1, 2, 3]);
  assert.equal(r.fwd[3], 0, 'last step goes against s3 -> s2');
});

test('avoid skips links that are only unmatched', () => {
  const g = tinyGraph();
  assert.ok(routeSearch(g, [0], [3], { either: true }));
  assert.equal(routeSearch(g, [0], [3], { either: true, avoid: true }), null);
});

test('multi-source: any start, any destination', () => {
  const g = tinyGraph();
  const { path } = routeSearch(g, [3, 1], [2]);
  assert.equal(path.length, 2, 'one hop from whichever start is closest');
  assert.ok([3, 1].includes(path[0]) && path[1] === 2);
});

test('caller counts', () => {
  const g = tinyGraph();
  assert.equal(callerCount(g, 2), 2);
  assert.equal(callerCount(g, 0), 0);
});
