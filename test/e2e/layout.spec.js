import { test, expect } from './fixtures.js';

const overlaps = (a, b) => !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);

for (const width of [420, 851, 1280]) {
  test(`toolbar never covers search at ${width}px`, async ({ atlas }) => {
    await atlas.setViewportSize({ width, height: 860 });
    await atlas.open();
    const [s, t] = await Promise.all(
      ['.search', '.toolbar'].map(sel => atlas.locator(sel).evaluate(el => el.getBoundingClientRect().toJSON())),
    );
    expect(overlaps(s, t)).toBe(false);
  });
}

test('Key rows stay inside the Key card', async ({ atlas }) => {
  await atlas.open();
  const card = await atlas.locator('#legend').evaluate(el => el.getBoundingClientRect().right);
  const rows = await atlas
    .locator('#legendBody .lg-row')
    .evaluateAll(els => els.map(e => e.getBoundingClientRect().right));
  for (const r of rows) expect(r).toBeLessThanOrEqual(card);
});

test('the directions panel scrolls instead of clipping', async ({ atlas }) => {
  await atlas.setViewportSize({ width: 1280, height: 640 });
  await atlas.open('#self-route-r3-r4');
  const lastStepVisible = await atlas.locator('#route .lp-body').evaluate(b => {
    b.scrollTop = b.scrollHeight;
    const p = b.closest('#route').getBoundingClientRect(),
      s = b.querySelector('.step:last-child').getBoundingClientRect();
    return s.bottom <= p.bottom + 1;
  });
  expect(lastStepVisible).toBe(true);
});
