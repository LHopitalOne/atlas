import { test, expect } from './fixtures.js';

test.use({
  viewport: { width: 390, height: 844 },
  isMobile: true,
  hasTouch: true,
  contextOptions: { reducedMotion: 'reduce' },
});

test('on a phone, Ask and Directions are bottom sheets that leave the map visible above', async ({ atlas }) => {
  await atlas.open('#self-route-r3-r4');
  const r = await atlas.locator('#route').evaluate(el => el.getBoundingClientRect().toJSON());
  expect(r.top).toBeGreaterThan(844 * 0.3);
  await atlas.locator('#route [data-rclose]').tap();
  await atlas.locator('#q').tap();
  await atlas.keyboard.type('How are we rendering the graph?');
  await atlas.keyboard.press('Enter');
  const a = await atlas.locator('#ask').evaluate(el => el.getBoundingClientRect().toJSON());
  expect(a.top).toBeGreaterThan(844 * 0.3);
  await expect(atlas.locator('#ask .sources summary')).toBeVisible();
});

test('on a phone, the inspector title takes focus without an outline', async ({ atlas }) => {
  await atlas.open();
  await atlas.locator('#q').tap();
  await atlas.keyboard.type('routeSearch');
  await atlas
    .locator('#results [role="option"]', { hasText: /^routeSearch/ })
    .first()
    .tap();
  await expect(atlas.locator('#insTitle')).toBeFocused();
  const style = await atlas.locator('#insTitle').evaluate(el => getComputedStyle(el).outlineStyle);
  expect(style).toBe('none');
});
