import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tinySpec, tinyGraph } from './helpers.js';
import { build, distribute, sizesFor } from '../src/model/synthetic.js';
import { buildSpec, validateSpec } from '../src/model/spec.js';
import { readFileSync } from 'node:fs';

test('distribute keeps the total and the minimum', () => {
  const out = distribute(100, [1, 2, 7], 5);
  assert.equal(
    out.reduce((a, b) => a + b, 0),
    100,
  );
  assert.ok(Math.min(...out) >= 5);
});

test('synthetic graphs are deterministic and sized as promised', () => {
  const a = build(5000),
    b = build(5000);
  assert.equal(a.N, 5000);
  assert.deepEqual([a.S, a.R, a.D], [sizesFor(5000).S, sizesFor(5000).R, sizesFor(5000).D]);
  assert.deepEqual(Array.from(a.PX.slice(0, 50)), Array.from(b.PX.slice(0, 50)));
  assert.equal(a.L + a.C, Math.round(5000 * 1.62), 'edges = containment + contracts');
  assert.equal(
    a.BYST.reduce((x, y) => x + y, 0),
    a.C,
  );
});

test('layout invariants: territories never overlap, endpoints sit on their service', () => {
  const g = build(5000);
  for (let a = 0; a < g.R; a++)
    for (let b = a + 1; b < g.R; b++)
      assert.ok(
        Math.hypot(g.rx[a] - g.rx[b], g.ry[a] - g.ry[b]) >= g.rR[a] + g.rR[b] - 1e-3,
        `repos ${a} and ${b} overlap`,
      );
  for (let r = 0; r < g.R; r++)
    for (let a = g.rDs[r]; a < g.rDe[r]; a++)
      for (let b = a + 1; b < g.rDe[r]; b++)
        assert.ok(
          Math.hypot(g.dcx[a] - g.dcx[b], g.dcy[a] - g.dcy[b]) >= g.dR[a] + g.dR[b] - 1e-2,
          `domains ${a} and ${b} overlap`,
        );
  for (let i = g.S; i < g.N; i++) {
    const s = g.own(i);
    assert.ok(Math.hypot(g.PX[i] - g.PX[s], g.PY[i] - g.PY[s]) <= g.RF[s]);
  }
});

test('spec graphs: ids, names and aggregates', () => {
  const g = tinyGraph();
  assert.deepEqual([g.N, g.S, g.R, g.D, g.C], [7, 4, 2, 3, 3]);
  assert.equal(g.name(5), 'l1');
  assert.equal(g.own(6), 1);
  assert.equal(g.dr.n, 3, 'directed service pairs');
  assert.equal(g.ISS[3], 2, 'unresolved link marks both ends');
});

test('validateSpec explains problems', () => {
  assert.deepEqual(validateSpec(tinySpec()), []);
  const bad = tinySpec();
  bad.edges.push([1, 99, 0], [0, 1, 7]);
  const errs = validateSpec(bad);
  assert.ok(errs.some(e => e.includes('outside')) && errs.some(e => e.includes('status 7')));
  assert.throws(() => buildSpec(bad), /Invalid graph spec/);
});

test('an edge a SCIP index shows carries a fourth item, counted apart', () => {
  const spec = tinySpec();
  spec.edges[0] = [...spec.edges[0], 1];
  const g = buildSpec(spec);
  assert.equal(g.SCIPN, 1);
  assert.deepEqual([...g.CPR], [1, ...Array(spec.edges.length - 1).fill(0)]);
  spec.edges[1] = [...spec.edges[1], 5];
  assert.ok(validateSpec(spec).some(e => e.includes('seen by SCIP')));
});

test('the embedded self graph is a valid spec', () => {
  const spec = JSON.parse(readFileSync('generated/self-graph.json', 'utf8'));
  assert.deepEqual(validateSpec(spec), []);
  assert.ok(buildSpec(spec).N > 500);
});

test('a service may carry tags, shown with its summary', () => {
  const spec = tinySpec();
  const first = spec.repos[0].domains[0].services[0];
  first.doc = 'Creates orders.';
  first.tags = ['api', 'orders'];
  const g = buildSpec(spec);
  assert.deepEqual(g.tags(0), ['api', 'orders']);
  assert.deepEqual(g.tags(1), []);
  first.tags = 'api';
  assert.match(validateSpec(spec).join('\n'), /tags must be a list of strings/);
});
