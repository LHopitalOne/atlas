// A graph made by Graphify and converted by bridge/ (test/fixtures/graphify-shop.json, kept current by
// bridge/tests/test_cli.py) draws, names its source and repositories, and is searchable.
import { readFileSync } from 'node:fs';
import { test, expect } from './fixtures.js';

const SPEC = JSON.parse(readFileSync('test/fixtures/graphify-shop.json', 'utf8'));

test('a Graphify graph converted by the bridge draws and is searchable', async ({ atlas }) => {
  await atlas.open();
  await atlas.evaluate(spec => window.Atlas.loadGraph(spec), SPEC);
  await expect(atlas.locator('#count')).toContainText('16');
  await expect(atlas.locator('#scale [data-v="self"]')).toHaveText('Graphify');
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('OrderStore');
  await expect(atlas.locator('#results')).toContainText('OrderStore');
});
