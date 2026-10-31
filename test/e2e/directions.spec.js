import { test, expect } from './fixtures.js';

test('type a start and destination, get a route', async ({ atlas }) => {
  await atlas.open();
  await atlas.click('#dirBtn');
  await expect(atlas.locator('.rt-in[data-which="from"]')).toBeFocused();
  await atlas.keyboard.type('renderRoute');
  await expect(atlas.locator('#rtSug [role="option"]').first()).toContainText('renderRoute');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('.rt-in[data-which="to"]')).toBeFocused();
  await atlas.keyboard.type('drawNodes');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#route .rt-sum')).toContainText('hop');
  await expect(atlas).toHaveURL(/-route-\d+-\d+/);
});

test('repository to repository falls back to either direction and explains it', async ({ atlas }) => {
  await atlas.open('#self-route-r3-r4');
  await expect(atlas.locator('#route .rt-sum .big')).toContainText('hop');
  await expect(atlas.locator('#route .rt-legend')).toContainText('Dashed');
  await atlas.click('[data-detail="service"]');
  await expect(atlas).toHaveURL(/-byservice/);
});

test('closing directions clears the route', async ({ atlas }) => {
  await atlas.open('#25k-route-3995-3');
  await expect(atlas.locator('#route')).toHaveClass(/on/);
  await atlas.click('[data-rclose]');
  await expect(atlas.locator('#route')).not.toHaveClass(/on/);
  await expect(atlas).toHaveURL(/#25k$/);
});
