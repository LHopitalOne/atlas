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

const box = (page, sel) => page.locator(sel).evaluate(el => el.getBoundingClientRect().toJSON());

async function openSourceOf(page, name) {
  await page.keyboard.press('/');
  await page.keyboard.type(name);
  await page
    .locator('#results [role="option"]', { hasText: new RegExp(`^${name}`) })
    .first()
    .click();
  await page.click('.actions [data-source]');
  await page.waitForTimeout(400);
}

for (const width of [960, 1280]) {
  test(`source view sits below the toolbar and beside the inspector at ${width}px`, async ({ atlas }) => {
    await atlas.setViewportSize({ width, height: 860 });
    await atlas.open();
    await openSourceOf(atlas, 'controlsHTML');
    const [code, toolbar, insp] = await Promise.all(['#code', '.toolbar', '#insp'].map(s => box(atlas, s)));
    expect(overlaps(code, toolbar)).toBe(false);
    expect(overlaps(code, insp)).toBe(false);
  });
}

test('source view: line numbers stay visible when scrolling sideways, the definition is highlighted across the line', async ({
  atlas,
}) => {
  await atlas.open();
  await openSourceOf(atlas, 'controlsHTML');
  const r = await atlas.evaluate(() => {
    const body = document.querySelector('#code .cv-body'),
      def = document.querySelector('#code .ln.def');
    body.scrollLeft = 300;
    const no = def.querySelector('.no').getBoundingClientRect().left - body.getBoundingClientRect().left;
    return {
      no: Math.round(no),
      full:
        Math.round(def.getBoundingClientRect().width) ===
        Math.round(document.querySelector('#code .code').getBoundingClientRect().width),
    };
  });
  expect(r.no).toBe(0);
  expect(r.full).toBe(true);
});

test('inspector content shares one left edge', async ({ atlas }) => {
  await atlas.open();
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('routeSearch');
  await atlas
    .locator('#results [role="option"]', { hasText: /^routeSearch/ })
    .first()
    .click();
  const lefts = await atlas.evaluate(() =>
    ['.about-text', '.sig', '.stats .stat', '.sec-h h3', '.impact-text', '[data-impact]'].map(s =>
      Math.round(document.querySelector('#insp ' + s).getBoundingClientRect().left),
    ),
  );
  expect(new Set(lefts).size).toBe(1);
});

for (const width of [840, 960]) {
  test(`with the inspector open, the Key and map controls never overlap at ${width}px`, async ({ atlas }) => {
    await atlas.setViewportSize({ width, height: 860 });
    await atlas.open('#5k-node-40');
    await atlas.waitForTimeout(500);
    const vis = sel =>
      atlas.locator(sel).evaluate(el => {
        const c = getComputedStyle(el);
        return c.visibility !== 'hidden' && +c.opacity > 0;
      });
    if (await vis('#legend')) expect(overlaps(await box(atlas, '#legend'), await box(atlas, '.navcard'))).toBe(false);
  });
}
