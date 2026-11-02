import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import './setup.js';
import { buildSpec } from '../src/model/spec.js';
import { loops, shortestLoop, cyclesOf, loopThrough } from '../src/graph/cycles.js';
import { build } from '../src/model/synthetic.js';

const adj = edges => (u, visit) => (edges[u] || []).forEach(visit);

test('components: a loop of three plus a tail; a self-contained pair', () => {
  const each = adj({ 0: [1], 1: [2], 2: [0, 3], 3: [], 4: [5], 5: [4] });
  const comps = loops(6, each).map(c => [...c].sort());
  assert.deepEqual(comps, [
    [0, 1, 2],
    [4, 5],
  ]);
});

test('shortest loop prefers the short way back', () => {
  const each = adj({ 0: [1, 3], 1: [2], 2: [0], 3: [0] });
  assert.deepEqual(shortestLoop(0, [0, 1, 2, 3], each), [0, 3, 0]);
});

test('no recursion limits on long chains', () => {
  const n = 50000,
    each = (u, visit) => visit((u + 1) % n);
  assert.equal(loops(n, each)[0].length, n);
});

test('services: a graph that only flows one way has no cycles', () => {
  const spec = {
    meta: {},
    repos: [{ name: 'A', domains: [{ name: 'a', services: [{ name: 's0' }, { name: 's1' }, { name: 's2' }] }] }],
    edges: [
      [0, 1, 0],
      [1, 2, 0],
    ],
  };
  const g = buildSpec(spec);
  assert.equal(cyclesOf(g).groups.length, 0);
  assert.equal(loopThrough(g, 1), null);
});

test('services: a loop is found, and loops through a member close on themselves', () => {
  const spec = {
    meta: {},
    repos: [
      {
        name: 'A',
        domains: [
          { name: 'a', services: [{ name: 's0' }, { name: 's1' }] },
          { name: 'b', services: [{ name: 's2' }] },
        ],
      },
    ],
    edges: [
      [0, 1, 0],
      [1, 2, 0],
      [2, 0, 0],
    ],
  };
  const g = buildSpec(spec);
  assert.equal(cyclesOf(g).groups.length, 1);
  const { loop, size } = loopThrough(g, 2);
  assert.equal(size, 3);
  assert.deepEqual([loop[0], loop.at(-1)], [2, 2]);
  assert.equal(cyclesOf(g, 'domain').groups[0].members.length, 2, 'domains a and b depend on each other');
});

test('real maps: Self and a 5k demo map have cycles, and every shown loop is made of real calls', () => {
  for (const g of [buildSpec(JSON.parse(readFileSync('generated/self-graph.json', 'utf8'))), build(5000)]) {
    const c = cyclesOf(g);
    assert.ok(c.groups.length > 0);
    for (const { loop } of c.groups.slice(0, 5))
      for (let k = 1; k < loop.length; k++) assert.ok(g.dr.map.has(loop[k - 1] * g.S + loop[k]), 'each step is a call');
  }
});
