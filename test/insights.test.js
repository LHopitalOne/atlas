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

test('an answer trail joins cited services in order through short chains', async () => {
  const { answerTrail } = await import('../src/graph/insights.js');
  const g = tinyGraph();
  // s0 -> s1 -> s2 <- s3 : citing s0, s2, s3 walks s0-s1-s2, then s2-s3 (against the call)
  const { hops, via } = answerTrail(g, [0, 2, 3]);
  assert.deepEqual(
    hops.map(h => [h.a, h.b]),
    [
      [0, 1],
      [1, 2],
      [2, 3],
    ],
  );
  assert.deepEqual(via, [1], 's1 is passed through but not named');
  assert.equal(hops[2].fwd, false);
  assert.deepEqual(answerTrail(g, [0, 3], 2).hops, [], 'pairs further apart than maxHops stay unjoined');
});

test('a loop keeps both directions of a pair; other trails draw a pair once', async () => {
  const { answerTrail } = await import('../src/graph/insights.js');
  const g = tinyGraph();
  // s0 -> s1: an answer going s0 > s1 > s0 (a cycle) draws there and back, as two arcs
  const loop = answerTrail(g, [0, 1, 0], 3, true).hops.map(h => [h.a, h.b]);
  assert.deepEqual(loop, [
    [0, 1],
    [1, 0],
  ]);
  assert.equal(answerTrail(g, [0, 1, 0]).hops.length, 1, 'without directed, the way back is the same line');
});

test('answer lines: domains get a line only when they call each other', async () => {
  const { answerHops } = await import('../src/graph/insights.js');
  const g = tinyGraph(); // domains a1=d0 (s0, s1), a2=d1 (s2), b1=d2 (s3): a1 calls a2, b1 calls a2, a1 and b1 never meet
  assert.deepEqual(answerHops(g, [['d0', 'd2']]).hops, [], 'two unrelated domains named together draw nothing');
  const linked = answerHops(g, [['d0', 'd1']]).hops;
  assert.equal(linked.length, 1);
  assert.deepEqual(linked[0].ends, [g.dcx[0], g.dcy[0], g.dcx[1], g.dcy[1]], 'drawn between the domain centres');
  // a diagram's domain loop keeps both directions; the same chain in plain text is drawn once
  assert.equal(answerHops(g, [['d0', 'd1', 'd0']], true).hops.length, 2);
  assert.equal(answerHops(g, [['d0', 'd1', 'd0']]).hops.length, 1);
});

test('answer lines: only a diagram makes a loop; plain text naming a service twice is drawn once', async () => {
  const { answerHops } = await import('../src/graph/insights.js');
  const g = tinyGraph(); // s0 -> s1
  // "s0 calls s1, so a change to s0 reaches it": cites s0, s1, s0 in one paragraph
  const prose = answerHops(g, [['n0', 'n1', 'n0']]);
  assert.deepEqual(
    prose.hops.map(h => [h.a, h.b]),
    [[0, 1]],
  );
  // the same refs as a diagram's loop (FLOW: n0 > n1 > n0): there and back, as two arcs
  const loop = answerHops(g, [['n0', 'n1', 'n0']], true);
  assert.deepEqual(
    loop.hops.map(h => [h.a, h.b]),
    [
      [0, 1],
      [1, 0],
    ],
  );
  assert.equal(loop.hops[1].fwd, false, 'the way back runs against the call');
});
