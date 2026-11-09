import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatHash, parseHash } from '../src/app/url-codec.js';

const base = {
  dataset: 'self',
  selectedId: -1,
  route: { from: null, to: null, avoid: false, links: 'calls', detail: 'service', detailSet: false },
  issuesOnly: false,
  colorMode: 'repo',
  userColor: false,
};

test('dataset only', () => {
  assert.equal(formatHash(base), 'self');
  assert.equal(formatHash({ ...base, dataset: 25000 }), '25k');
});

test('selection, issues and colour round-trip', () => {
  const h = formatHash({
    ...base,
    dataset: 5000,
    selectedId: 42,
    issuesOnly: true,
    colorMode: 'health',
    userColor: true,
  });
  assert.equal(h, '5k-node-42-issues-health');
  assert.deepEqual(parseHash('#' + h), { n: 5000, node: 42, issues: true, color: 'health' });
});

test('routes between territories and services round-trip', () => {
  const route = {
    from: { t: 'r', id: 3 },
    to: { t: 's', id: 127 },
    avoid: true,
    links: 'any',
    detail: 'domain',
    detailSet: true,
  };
  const h = formatHash({ ...base, route });
  assert.equal(h, 'self-route-r3-127-avoid-any-bydomain');
  const o = parseHash(h);
  assert.deepEqual(
    [o.from, o.to, o.avoid, o.any, o.detail],
    [{ t: 'r', id: 3 }, { t: 's', id: 127 }, true, true, 'domain'],
  );
});

test('unset route end and unknown tokens', () => {
  assert.deepEqual(parseHash('#25k-route-x-d7').from, null);
  assert.deepEqual(parseHash('#25k-route-x-d7').to, { t: 'd', id: 7 });
  assert.equal(parseHash('#Not_A-map!').n, 'self');
  // a lowercase word may name an embedded map; loadDataset falls back when no such map exists
  assert.equal(parseHash('#nonsense').n, 'nonsense');
  assert.equal(parseHash('#self-node-abc').node, -1);
});

test('only letters, digits and hyphens (survives artifact links)', () => {
  const h = formatHash({
    ...base,
    route: { from: { t: 'd', id: 1 }, to: null, avoid: false, links: 'calls', detail: 'service', detailSet: false },
  });
  assert.match(h, /^[A-Za-z0-9-]+$/);
});

test('embedded map keys round-trip', () => {
  const h = formatHash({ ...base, dataset: 'sentry', selectedId: 42 });
  assert.equal(h, 'sentry-node-42');
  assert.deepEqual([parseHash('#' + h).n, parseHash('#' + h).node], ['sentry', 42]);
});
