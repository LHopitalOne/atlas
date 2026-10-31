import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tinyGraph } from './helpers.js';
import { rolesOf, impactOf } from '../src/graph/insights.js';
import { build } from '../src/model/synthetic.js';

// tiny graph: s0 -> s1 -> s2 <- s3 ; s0, s1, s2 in repo A, s3 in repo B
test('roles from the graph', () => {
  const g = tinyGraph(),
    keys = s => rolesOf(g, s).map(r => r.key);
  assert.deepEqual(keys(0), ['entry']);
  assert.deepEqual(keys(2), ['deadEnd']);
  assert.deepEqual(keys(3), ['entry']);
  assert.deepEqual(keys(1), [], 'an ordinary middle service has no badge');
});

test('impact follows callers transitively, nearest first', () => {
  const g = tinyGraph();
  const im = impactOf(g, 2);
  assert.deepEqual(new Set(im.services), new Set([1, 3, 0]));
  assert.equal(im.services.at(-1), 0, 's0 is two steps away');
  assert.equal(im.direct, 2);
  assert.equal(im.repos, 2);
  assert.deepEqual(impactOf(g, 0).services, []);
});

test('hubs and bridges appear on a large graph', () => {
  const g = build(5000),
    seen = new Set();
  for (let s = 0; s < g.S; s++) for (const r of rolesOf(g, s)) seen.add(r.key);
  for (const k of ['entry', 'hub', 'bridge', 'deadEnd']) assert.ok(seen.has(k), k);
});

test('synthetic graphs carry simulated summaries', () => {
  const g = build(281);
  assert.equal(g.meta.docSource, 'simulated');
  assert.match(g.doc(0), /\w+.*\./);
  assert.match(g.doc(g.S), /\w+.*\./);
});

test('calling a library does not make a service a bridge', () => {
  // A: s0 -> s1 ; B (a library that calls nothing outside itself): s2 ; s1 -> s2, and C: s3 -> s1
  const spec = {
    meta: {},
    repos: [
      { name: 'A', domains: [{ name: 'a', services: [{ name: 's0' }, { name: 's1' }] }] },
      { name: 'Lib', domains: [{ name: 'l', services: [{ name: 's2' }] }] },
      { name: 'C', domains: [{ name: 'c', services: [{ name: 's3' }] }] },
    ],
    edges: [
      [0, 1, 0],
      [1, 2, 0],
      [3, 1, 0],
    ],
  };
  return import('../src/model/spec.js').then(({ buildSpec }) => {
    const g = buildSpec(spec);
    assert.ok(!rolesOf(g, 1).some(r => r.key === 'bridge'), 'C -> s1 -> Lib is not a bridge: Lib calls nothing onward');
  });
});
