import { test, expect } from './fixtures.js';

test('opens on Atlas’s own code graph by default', async ({ atlas }) => {
  await atlas.open();
  await expect(atlas).toHaveURL(/#self$/);
  await expect(atlas.locator('#scale [aria-checked="true"]')).toHaveText('Self');
  await expect(atlas.locator('#legendBody')).toContainText('Indexed with');
});

test('switching scale rebuilds the map and updates the link', async ({ atlas }) => {
  await atlas.open();
  await atlas.click('#scale [data-v="5000"]');
  await expect(atlas.locator('#count')).toContainText('5,000');
  await expect(atlas).toHaveURL(/#5k$/);
});

test('search selects a service and opens the inspector with focus on its title', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('renderRoute');
  await expect(atlas.locator('#results')).toContainText('renderRoute');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#insTitle')).toHaveText('renderRoute');
  await expect(atlas.locator('#insTitle')).toBeFocused();
  await expect(atlas).toHaveURL(/#self-node-\d+$/);
});

test('hovering while the map builds never throws', async ({ atlas }) => {
  await atlas.goto((await import('./fixtures.js')).PAGE + '#25k', { waitUntil: 'domcontentloaded' });
  for (let x = 100; x < 900; x += 40) await atlas.mouse.move(x, 400);
  await expect(atlas.locator('#count')).toContainText('25,000');
});

test('keyboard: the map takes focus and + zooms in', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('Tab');
  await expect(atlas.locator('#ov')).toBeFocused();
  const before = await atlas.locator('#zoom').inputValue();
  await atlas.keyboard.press('=');
  await expect.poll(async () => Number(await atlas.locator('#zoom').inputValue())).toBeGreaterThan(Number(before));
});

test('issues mode lists what needs attention', async ({ atlas }) => {
  await atlas.open();
  await atlas.click('#issues');
  await expect(atlas.locator('#attn')).toContainText('Needs attention');
  await expect(atlas.locator('#attn .row').first()).toBeVisible();
  await expect(atlas).toHaveURL(/-issues/);
});
