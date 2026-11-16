// Maps a build keeps in their own files (--external-maps): downloaded once, on first show; maps in the page need none.
import { test } from 'node:test';
import assert from 'node:assert/strict';

const SPEC = { meta: {}, repos: [], edges: [] };
const elements = {
  mapIndex: { textContent: JSON.stringify([{ key: 'inpage' }, { key: 'away' }, { key: 'broken' }]) },
  'map-inpage': { textContent: JSON.stringify(SPEC), dataset: {} },
  'map-away': { textContent: '', dataset: { src: 'maps/away.json' } },
  'map-broken': { textContent: '', dataset: { src: 'maps/broken.json' } },
};
globalThis.document = { getElementById: id => elements[id] || null };
const { loadMap, mapSource, mapSpec } = await import('../src/model/maps.js');

test('a map in the page has no file and loads without a request', async () => {
  const calls = [];
  assert.equal(mapSource('inpage'), '');
  await loadMap('inpage', url => calls.push(url));
  assert.deepEqual(calls, []);
  assert.deepEqual(mapSpec('inpage'), SPEC);
});

test('a map in its own file is downloaded once, then read like any other', async () => {
  const calls = [];
  const get = async url => (calls.push(url), { ok: true, json: async () => ({ ...SPEC, meta: { from: url } }) });
  assert.equal(mapSource('away'), 'maps/away.json');
  await loadMap('away', get);
  await loadMap('away', get);
  assert.deepEqual(calls, ['maps/away.json']);
  assert.equal(mapSource('away'), '');
  assert.equal(mapSpec('away').meta.from, 'maps/away.json');
});

test('a failed download says why and can be tried again', async () => {
  await assert.rejects(
    loadMap('broken', async () => ({ ok: false, status: 404, statusText: 'Not Found' })),
    /404 Not Found/,
  );
  assert.equal(mapSource('broken'), 'maps/broken.json');
});
