import { test, expect } from './fixtures.js';

test('answers play out: thinking, steps one by one, then the text streams in', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('How are we rendering the graph?');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#ask .steps.running li.now')).toBeVisible();
  await expect(atlas.locator('#ask .caret')).toBeVisible({ timeout: 10_000 });
  await expect(atlas.locator('#ask .ans-meta')).toBeVisible({ timeout: 20_000 });
  await expect(atlas.locator('#ask .caret')).toHaveCount(0);
});

test('Stop ends an answer where it is', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('How are we rendering the graph?');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#ask [data-send]')).toHaveAttribute('aria-label', 'Stop');
  await atlas.locator('#ask [data-send]').click();
  await expect(atlas.locator('#ask .ans-note')).toHaveText('Stopped.');
  await expect(atlas.locator('#ask [data-send]')).toHaveAttribute('aria-label', 'Send');
});
