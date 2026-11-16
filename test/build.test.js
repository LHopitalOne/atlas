import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

test('build embeds a graph containing "</script>" without breaking the page or the data', () => {
  const dir = mkdtempSync(join(tmpdir(), 'atlas-'));
  const spec = {
    meta: {},
    repos: [{ name: 'r', domains: [{ name: 'd', services: [{ name: 'evil</script><b>x', leaves: [] }] }] }],
    edges: [],
  };
  writeFileSync(join(dir, 'g.json'), JSON.stringify(spec));
  execFileSync('node', ['scripts/build.mjs', `--graph=${join(dir, 'g.json')}`, `--out=${join(dir, 'out.html')}`]);
  const html = readFileSync(join(dir, 'out.html'), 'utf8');
  const m = html.match(/<script type="application\/json" id="selfGraph">([\s\S]*?)<\/script>/);
  assert.ok(m, 'graph script tag is intact');
  assert.equal(JSON.parse(m[1]).repos[0].domains[0].services[0].name, 'evil</script><b>x');
});

test('--external-maps writes each map beside the page and leaves only its file name in the page', () => {
  const dir = mkdtempSync(join(tmpdir(), 'atlas-'));
  const spec = { meta: {}, repos: [], edges: [], links: [] };
  writeFileSync(join(dir, 'shop.json'), JSON.stringify(spec));
  const out = join(dir, 'site', 'index.html');
  execFileSync('node', [
    'scripts/build.mjs',
    `--maps=shop:${join(dir, 'shop.json')}:Shop`,
    '--external-maps',
    `--out=${out}`,
  ]);
  const html = readFileSync(out, 'utf8');
  assert.match(html, /<script type="application\/json" id="map-shop" data-src="maps\/shop\.json"><\/script>/);
  assert.deepEqual(JSON.parse(readFileSync(join(dir, 'site', 'maps', 'shop.json'), 'utf8')), spec);
});
