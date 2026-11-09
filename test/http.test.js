import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import './setup.js';
import { buildSpec, validateSpec } from '../src/model/spec.js';
import { arcDistance, groupsFrom, httpImpact, proofCounts, repoPairs, siteUrl } from '../src/model/http.js';

// test/fixtures/http-shop.json: web calls api twice (one confirmed by SCIP, one inferred) and once with no route
const SPEC = JSON.parse(readFileSync('test/fixtures/http-shop.json', 'utf8'));
const g = buildSpec(SPEC);
const H = g.http;
const byName = name => [...Array(g.N).keys()].find(i => g.name(i) === name);

test('links are grouped by the arc they draw, each on a real contract', () => {
  assert.equal(H.groups.length, 2);
  for (const gr of H.groups) assert.ok(gr.e >= 0 && g.CS[gr.e] === gr.from && g.CD[gr.e] === gr.to);
  assert.deepEqual(proofCounts(H), { scip: 1, inferred: 1 });
  assert.equal(H.unmatched.length, 1);
  assert.equal(H.accuracy.found, 2);
});

test('impact: what in other repositories calls an endpoint, a file or a repository', () => {
  const post = byName('POST /orders'),
    main = g.own(post),
    api = g.domRepo[g.svcDom[main]];
  assert.equal(httpImpact(g, H, { t: 'n', id: post }).links.length, 1);
  const file = httpImpact(g, H, { t: 'n', id: main });
  assert.deepEqual([file.endpoints.length, file.links.length, file.repos.length], [2, 2, 1]);
  assert.equal(httpImpact(g, H, { t: 'r', id: api }).groups.length, 2);
  assert.equal(httpImpact(g, H, { t: 'r', id: 1 - api }).groups.length, 0);
  assert.equal(groupsFrom(g, H, byName('placeOrder()')).length, 1);
  assert.deepEqual(
    repoPairs(g, H).map(p => [g.repoName[p.a], g.repoName[p.b], p.groups.length]),
    [['web', 'api', 2]],
  );
});

test('cited lines link to GitHub at the pinned commit, or nowhere without one', () => {
  const l = H.links[0];
  assert.equal(siteUrl(H, l.call), `https://github.com/example/shop-web/blob/${'2'.repeat(40)}/src/api.js#L5`);
  assert.equal(siteUrl({ repos: [{ url: '', commit: '' }] }, { repo: 0, file: 'a', line: 1 }), '');
});

test('arc picking measures distance to the drawn curve', () => {
  assert.ok(arcDistance(0, 0, 0, 0, 100, 0) < 1);
  assert.ok(arcDistance(50, 9, 0, 0, 100, 0) < 1); // the curve bulges to one side of the chord, halfway to its control point
  assert.ok(arcDistance(50, -20, 0, 0, 100, 0) > 19);
});

test('malformed links are reported', () => {
  const bad = structuredClone(SPEC);
  bad.links[0].proof = 'vibes';
  bad.links[1].to = 1e9;
  const errs = validateSpec(bad);
  assert.ok(errs.some(e => /proof vibes/.test(e)));
  assert.ok(errs.some(e => /links\[1\] needs from and to/.test(e)));
  assert.deepEqual(validateSpec({ ...SPEC, links: 'x' }).slice(-1), ['spec.links must be an array']);
});
