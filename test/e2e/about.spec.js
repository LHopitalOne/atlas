import { test, expect } from './fixtures.js';

/** Select a service by name through search (services are listed after domains). */
async function selectService(page, name) {
  await page.keyboard.press('/');
  await page.keyboard.type(name);
  await page.locator('#results [role="option"]', { hasText: new RegExp(`^${name}`) }).first().click();
  await expect(page.locator('#insTitle')).toHaveText(name);
}

test('the inspector says what a definition does, where that came from, and its signature', async ({ atlas }) => {
  await atlas.open();
  await selectService(atlas, 'routeSearch');
  await expect(atlas.locator('#insp .about-text')).toContainText('breadth-first');
  await expect(atlas.locator('#insp .prov')).toContainText('doc comment');
  await expect(atlas.locator('#insp .sig')).toContainText('routeSearch(g, src, tgt');
});

test('impact: how far a change reaches, and showing it on the map', async ({ atlas }) => {
  await atlas.open();
  await selectService(atlas, 'routeSearch');
  await expect(atlas.locator('#insp .impact-text')).toContainText(/affect \d+ services/);
  await atlas.click('[data-impact]');
  await expect(atlas.locator('[data-impact]')).toHaveAttribute('aria-pressed', 'true');
  await atlas.click('[data-impact]');
  await expect(atlas.locator('[data-impact]')).toHaveAttribute('aria-pressed', 'false');
});

test('source view: definition lines marked, labelled as live and not stored, Escape closes only it', async ({ atlas }) => {
  await atlas.open();
  await selectService(atlas, 'routeSearch');
  await atlas.click('.actions [data-source]');
  await expect(atlas.locator('#code')).toBeVisible();
  await expect(atlas.locator('#code .cv-prov')).toContainText('not stored');
  await expect(atlas.locator('#code .ln.def').first()).toContainText('export function routeSearch');
  await atlas.keyboard.press('Escape');
  await expect(atlas.locator('#code')).toBeHidden();
  await expect(atlas.locator('#insTitle')).toHaveText('routeSearch');
});

test('Copy for AI copies a structured description', async ({ atlas }) => {
  await atlas.open();
  await atlas.evaluate(() => { navigator.clipboard.writeText = t => { window.__copied = t; return Promise.resolve(); }; });
  await selectService(atlas, 'routeSearch');
  await atlas.click('[data-copy-ai]');
  const text = await atlas.evaluate(() => window.__copied);
  for (const part of ['# routeSearch', 'Summary:', 'Signature:', 'Impact:', 'Used by:', 'Source: graph/route-search.js']) expect(text).toContain(part);
});

test('search finds things by what they do', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('label collision');
  await expect(atlas.locator('#results')).toContainText('By what it does');
  await expect(atlas.locator('#results')).toContainText('CollisionGrid');
});

test('demo data: simulated summaries are labelled, and there is no source to show', async ({ atlas }) => {
  await atlas.open('#5k-node-40');
  await expect(atlas.locator('#insp .prov')).toContainText('simulated');
  await expect(atlas.locator('.actions [data-source]')).toBeDisabled();
});
