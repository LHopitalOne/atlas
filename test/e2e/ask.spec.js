import { test, expect } from './fixtures.js';

// answers play instantly with reduced motion; test/e2e/ask-playback.spec.js covers the animation
test.use({ contextOptions: { reducedMotion: 'reduce' } });

async function askFromSearch(page, q) {
  await page.keyboard.press('/');
  await page.keyboard.type(q);
  await expect(page.locator('#results [role="option"]').first()).toContainText(`Ask Atlas: ${q}`);
  await page.keyboard.press('Enter');
  await expect(page.locator('#ask')).toHaveClass(/on/);
}

test('a question in the search bar opens Ask Atlas with a cited answer', async ({ atlas }) => {
  await atlas.open();
  await askFromSearch(atlas, 'What breaks if I change routeSearch?');
  await expect(atlas.locator('#ask .ans-text')).toContainText(/can affect \d+ services/);
  await expect(atlas.locator('#ask .cite').first()).toBeVisible();
  expect(await atlas.locator('#ask .src').count()).toBe(await atlas.locator('#ask .sources .src').count());
  await expect(atlas.locator('#ask .ask-mode')).toHaveText('Demo');
  await expect(atlas.locator('#ask .ans-meta')).toContainText('Simulated');
  expect(await atlas.locator('#legend').evaluate(d => d.open)).toBe(false);
});

test('names in the search bar still search; asking is offered last', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('routeSearch');
  await expect(atlas.locator('#results [role="option"]').last()).toContainText('Ask Atlas: routeSearch');
  await expect(atlas.locator('#results [role="option"]').first()).not.toContainText('Ask Atlas');
});

test('citations lead to the map; "this" means the selection', async ({ atlas }) => {
  await atlas.open();
  await askFromSearch(atlas, 'What breaks if I change routeSearch?');
  // the numbered chips in the text are the way in (sources are folded)
  await atlas.locator('#ask .cite').first().click();
  await expect(atlas.locator('#insTitle')).toHaveText('routeSearch');
  await expect(atlas.locator('#ask .ctx')).toContainText('routeSearch');
  await atlas.locator('#ask textarea').fill('what does this do?');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#ask .turn').nth(1).locator('.ans-text')).toContainText('breadth-first');
});

test('answers show on the map, the button toggles it; @ mentions complete names', async ({ atlas }) => {
  await atlas.open();
  await askFromSearch(atlas, 'who uses store?');
  // answers light up their items on the map when they finish; the button toggles that
  await expect(atlas.locator('#ask [data-show]')).toHaveAttribute('aria-pressed', 'true');
  await atlas.locator('#ask [data-show]').click();
  await expect(atlas.locator('#ask [data-show]')).toHaveAttribute('aria-pressed', 'false');
  await atlas.locator('#ask [data-show]').click();
  await expect(atlas.locator('#ask [data-show]')).toHaveAttribute('aria-pressed', 'true');
  await atlas.locator('#ask textarea').click();
  await atlas.keyboard.type('how does @placeL');
  await expect(atlas.locator('#ask .mentions')).toBeVisible();
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#ask textarea')).toHaveValue(/@placeLabels $/);
});

test('one left panel at a time, and Escape closes Ask', async ({ atlas }) => {
  await atlas.open();
  await askFromSearch(atlas, 'what is this codebase?');
  await expect(atlas.locator('#ask .ans-text')).toContainText('repositories');
  await atlas.locator('#ask textarea').click();
  await atlas.keyboard.press('Escape');
  await expect(atlas.locator('#ask')).not.toHaveClass(/on/);
  await atlas.keyboard.press('a');
  await expect(atlas.locator('#ask')).toHaveClass(/on/);
  await atlas.locator('#ask textarea').blur();
  await atlas.click('#dirBtn');
  await expect(atlas.locator('#route')).toHaveClass(/on/);
  await expect(atlas.locator('#ask')).not.toHaveClass(/on/);
});

test('the rendering walkthrough cites the real pipeline and lights it up on the map', async ({ atlas }) => {
  await atlas.open();
  await askFromSearch(atlas, 'How are we rendering the graph? The end-to-end flow');
  await expect(atlas.locator('#ask .steps summary')).toHaveText(/Looked at 6 things · read code live/);
  for (const name of ['buildScene', 'requestRender', 'drawOverlay', 'placeLabels'])
    await expect(atlas.locator('#ask .sources')).toContainText(name);
  await expect(atlas.locator('#ask [data-show]')).toHaveAttribute('aria-pressed', 'true');
});

test('the walkthrough is the first suggestion on the Self map', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('a');
  await expect(atlas.locator('#ask .ask-empty .chip-q').first()).toHaveText(
    'How are we rendering the graph? The end-to-end flow',
  );
});

test('the A shortcut opens Ask without typing an "a"', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('a');
  await expect(atlas.locator('#ask textarea')).toBeFocused();
  await expect(atlas.locator('#ask textarea')).toHaveValue('');
});

test('suggestions on a demo map are answerable', async ({ atlas }) => {
  await atlas.open('#5k');
  await atlas.keyboard.press('a');
  const route = atlas.locator('#ask .ask-empty .chip-q', { hasText: /^How does/ });
  await route.click();
  await expect(atlas.locator('#ask .ans-text')).toContainText(/hops?/);
});

test('sources start folded to one line and stay open once opened', async ({ atlas }) => {
  await atlas.open();
  await askFromSearch(atlas, 'How are we rendering the graph?');
  const src = atlas.locator('#ask .sources');
  await expect(src.locator('summary')).toContainText('17 sources');
  expect(await src.evaluate(d => d.open)).toBe(false);
  await src.locator('summary').click();
  await expect(src.locator('.src').first()).toBeVisible();
});

test('ordered answers draw a step line; Copy as Mermaid copies a flowchart', async ({ atlas }) => {
  await atlas.open();
  await atlas.evaluate(() => {
    navigator.clipboard.writeText = t => {
      window.__copied = t;
      return Promise.resolve();
    };
  });
  await askFromSearch(atlas, 'How are we rendering the graph?');
  await expect(atlas.locator('#ask .flow .fs')).toHaveCount(6);
  await expect(atlas.locator('#ask .flow .ft').first()).toHaveText('Data');
  await atlas.locator('#ask .flow .fchip', { hasText: 'buildScene' }).click();
  await expect(atlas.locator('#insTitle')).toHaveText('buildScene');
  await atlas.locator('#ask [data-mermaid]').click();
  const text = await atlas.evaluate(() => window.__copied);
  expect(text).toContain('flowchart TD');
  expect(text).toContain('subgraph');
});
