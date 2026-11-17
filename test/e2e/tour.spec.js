// The welcome tour on pages built with --tour: it dims the page and lights one part, waits for a real link click,
// switches maps, offers a question whose answer is a diagram, and stays closed once skipped. Builds without --tour
// never show it.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { test, expect } from './fixtures.js';

const TOUR_PAGE = resolve('dist/test-tour.html');
const NO_LINKS_PAGE = resolve('dist/test-tour-no-links.html'); // a second map with no HTTP links at all
const SPLIT_PAGE = resolve('dist/test-tour-split/index.html'); // maps downloaded from maps/<key>.json
const PLAIN_PAGE = resolve('dist/test-no-tour.html');
// two maps with links (the same shop twice), so the tour has a map to switch to and asks a route question there
const MAPS = 'shop:test/fixtures/http-shop.json:Shop,again:test/fixtures/http-shop.json:Shop again';

test.beforeAll(() => {
  execFileSync('node', ['scripts/build.mjs', '--offline', `--maps=${MAPS}`, '--tour', `--out=${TOUR_PAGE}`]);
  execFileSync('node', ['scripts/build.mjs', '--offline', `--maps=${MAPS}`, `--out=${PLAIN_PAGE}`]);
  const noLinks = 'shop:test/fixtures/http-shop.json:Shop,plain:test/fixtures/graphify-shop.json:Plain';
  execFileSync('node', ['scripts/build.mjs', '--offline', `--maps=${noLinks}`, '--tour', `--out=${NO_LINKS_PAGE}`]);
  execFileSync('node', [
    'scripts/build.mjs',
    '--offline',
    `--maps=${MAPS}`,
    '--tour',
    '--external-maps',
    `--out=${SPLIT_PAGE}`,
  ]);
});

async function openTour(page) {
  await page.goto(pathToFileURL(TOUR_PAGE).href);
  await expect(page.locator('#count')).toContainText('nodes');
  await expect(page.locator('.tour-card')).toBeVisible();
}

const card = page => page.locator('.tour-card');
const box = (page, sel) => page.locator(sel).evaluate(el => el.getBoundingClientRect().toJSON());
/** How far the closest lit part is from the target's box plus the spotlight's margin (6 px), at its worst edge. */
const lightOff = (page, sel) =>
  page.evaluate(s => {
    const b = document.querySelector(s).getBoundingClientRect();
    const off = a =>
      Math.max(
        Math.abs(a.left - (b.left - 6)),
        Math.abs(a.top - (b.top - 6)),
        Math.abs(a.right - Math.min(innerWidth, b.right + 6)),
        Math.abs(a.bottom - Math.min(innerHeight, b.bottom + 6)),
      );
    return Math.min(...[...document.querySelectorAll('.tour-shade rect')].map(r => off(r.getBoundingClientRect())));
  }, sel);
const litParts = page => page.locator('.tour-shade rect').count();
/** The element a click at (x, y) would reach. */
const hitAt = (page, x, y) =>
  page.evaluate(
    ([px, py]) => {
      const el = document.elementFromPoint(px, py);
      return el.closest('.tour-shade') ? 'dim' : el.closest('#links') ? 'links' : el.tagName;
    },
    [x, y],
  );

test('shows on the first visit: a welcome over a light dim, then each step lights its part and blocks the rest', async ({
  atlas,
}) => {
  await openTour(atlas);
  await expect(card(atlas)).toContainText('1 of 5');
  await expect(card(atlas)).toContainText('Welcome to Atlas');
  await expect(card(atlas)).toContainText('This is Shop: two repositories mapped by Graphify');
  // the welcome lights nothing, dims lightly, sits in the middle, and the links panel waits for its own step
  expect(await litParts(atlas)).toBe(0);
  await expect(atlas.locator('.tour')).toHaveClass(/soft/);
  await expect(atlas.locator('#links')).toBeHidden();
  const vp = atlas.viewportSize();
  await expect
    .poll(async () => {
      const c = await box(atlas, '.tour-card');
      return Math.abs(c.x + c.width / 2 - vp.width / 2);
    })
    .toBeLessThan(2);
  expect(await hitAt(atlas, vp.width / 2, 40)).toBe('dim');
  await expect(card(atlas)).toBeFocused();
  // step 2 lights the links panel: the light matches the panel, a click inside reaches it, outside hits the dim
  await card(atlas).getByRole('button', { name: 'Start the tour' }).click();
  await expect(atlas.locator('.tour')).not.toHaveClass(/soft/);
  // the card waits hidden while its panel slides in, then takes focus, so keyboard users can go on
  await expect(card(atlas)).toBeFocused();
  await expect(card(atlas)).toContainText('Click a link');
  const panel = await box(atlas, '#links');
  await expect.poll(() => lightOff(atlas, '#links')).toBeLessThan(2);
  expect(await hitAt(atlas, panel.x + panel.width / 2, panel.y + 30)).toBe('links');
  const vw = atlas.viewportSize().width;
  expect(await hitAt(atlas, vw / 2 + 100, 300)).toBe('dim');
});

test('the link step moves on only when a real link is clicked, then lights its proof and the link', async ({
  atlas,
}) => {
  await openTour(atlas);
  await card(atlas).getByRole('button', { name: 'Start the tour' }).click();
  await expect(card(atlas)).toContainText('Waiting for you to click a link');
  // clicking elsewhere in the panel, or the card's button (it focuses the first link), does not move on
  await atlas.locator('#links h2').click();
  // closing the panel while it is the target opens it again
  await atlas.locator('#links [data-lclose]').click();
  await expect(atlas.locator('#links [data-link]').first()).toBeVisible();
  // the button focuses the best-proven link (confirmed by SCIP), not an inferred one listed first
  await card(atlas).getByRole('button', { name: 'Choose a link' }).click();
  const best = atlas.locator('#links [data-link]:focus');
  await expect(best).toContainText('Confirmed by SCIP');
  await expect(card(atlas)).toContainText('2 of 5');
  await best.click();
  await expect(card(atlas)).toContainText('3 of 5');
  await expect(card(atlas)).toContainText('The proof');
  await expect(atlas.locator('#insp .site').first()).toContainText('Sends the request');
  await expect.poll(() => lightOff(atlas, '#insp')).toBeLessThan(2);
  // the link itself is lit on the map too, as a second lit part beside the proof
  await expect.poll(() => litParts(atlas)).toBe(2);
});

test('switches maps, then offers a question whose answer draws a diagram', async ({ atlas }) => {
  await openTour(atlas);
  const next = () => card(atlas).locator('[data-tour="next"]').click();
  await next();
  await atlas.locator('#links [data-link]').first().click();
  await expect(card(atlas)).toContainText('The proof');
  await next();
  await expect(card(atlas)).toContainText('Switch to Shop again');
  await card(atlas).getByRole('button', { name: 'Show Shop again' }).click();
  await expect(atlas.locator('#scale [data-v="again"]')).toHaveAttribute('aria-checked', 'true');
  await expect(card(atlas)).toContainText('5 of 5');
  await expect(atlas.locator('#ask')).toBeVisible();
  const q = card(atlas).locator('[data-tour="ask"]');
  await expect(q).toHaveText('How does web reach api?');
  await q.click();
  await expect(atlas.locator('#ask .uq')).toHaveText('How does web reach api?');
  await expect(atlas.locator('#ask .gv svg .gn')).toHaveCount(2, { timeout: 10000 });
  await card(atlas).getByRole('button', { name: 'Finish' }).click();
  await expect(atlas.locator('.tour')).toBeHidden();
});

test('Skip closes it for good; the Tour button plays it again; Escape closes it', async ({ atlas }) => {
  await openTour(atlas);
  await card(atlas).getByRole('button', { name: 'Skip tour' }).click();
  await expect(atlas.locator('.tour')).toBeHidden();
  await atlas.reload();
  await expect(atlas.locator('#count')).toContainText('nodes');
  await atlas.waitForTimeout(1500);
  await expect(atlas.locator('.tour')).toBeHidden();
  await atlas.locator('#tourBtn').click();
  await expect(card(atlas)).toContainText('1 of 5');
  await atlas.keyboard.press('Escape');
  await expect(atlas.locator('.tour')).toBeHidden();
  // Escape closed only the tour: the links panel is still open
  await expect(atlas.locator('#links')).toBeVisible();
});

test('on a phone the card is a sheet clear of the lit panel', async ({ atlas }) => {
  await atlas.setViewportSize({ width: 375, height: 812 });
  await openTour(atlas);
  await expect(atlas.locator('#tourBtn')).toBeVisible();
  await card(atlas).locator('[data-tour="next"]').click();
  await expect(card(atlas)).toContainText('Click a link');
  await expect.poll(async () => (await box(atlas, '.tour-card')).x).toBe(8); // after its entrance
  const c = await box(atlas, '.tour-card'),
    panel = await box(atlas, '#links');
  expect(c.width).toBe(375 - 16);
  expect(c.y + c.height).toBeLessThanOrEqual(panel.y); // the panel is a bottom sheet, so the card goes on top
  const toolbar = await box(atlas, '.toolbar');
  expect(toolbar.x + toolbar.width).toBeLessThanOrEqual(375);
});

test('a build without --tour shows no tour and no Tour button', async ({ atlas }) => {
  await atlas.goto(pathToFileURL(PLAIN_PAGE).href);
  await expect(atlas.locator('#count')).toContainText('nodes');
  await atlas.waitForTimeout(1500);
  await expect(atlas.locator('.tour')).toHaveCount(0);
  await expect(atlas.locator('#tourBtn')).toBeHidden();
});

/** Click through to the switch step: start, open a link's proof, then Next. */
async function toSwitchStep(page, other) {
  const next = () => card(page).locator('[data-tour="next"]').click();
  await next();
  await page.locator('#links [data-link]').first().click();
  await expect(card(page)).toContainText('The proof');
  await next();
  await expect(card(page)).toContainText(`Switch to ${other}`);
}

test('a map that fails to download does not leave the switch step stuck', async ({ atlas }) => {
  // a browser fetches maps beside a page only over http, so serve the split build (as on Vercel)
  const server = createServer((req, res) => {
    try {
      res.end(readFileSync(join(dirname(SPLIT_PAGE), new URL(req.url, 'http://x').pathname.slice(1) || 'index.html')));
    } catch {
      res.writeHead(404).end();
    }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  try {
    let fail = true;
    await atlas.route('**/maps/again.json', r => (fail ? r.fulfill({ status: 404, body: '' }) : r.continue()));
    await atlas.goto(`http://127.0.0.1:${server.address().port}/`);
    await expect(card(atlas)).toBeVisible();
    await toSwitchStep(atlas, 'Shop again');
    const show = card(atlas).getByRole('button', { name: 'Show Shop again' });
    await show.click();
    await expect(atlas.locator('.toast')).toContainText('Could not download Shop again');
    // still on the switch step, not stuck loading: Next works again, and a second try that succeeds moves on
    await expect(card(atlas)).toContainText('4 of 5');
    await expect(card(atlas)).not.toContainText('Loading the map');
    await expect(show).not.toHaveAttribute('aria-disabled', 'true');
    fail = false;
    await show.click();
    await expect(card(atlas)).toContainText('5 of 5');
  } finally {
    server.close();
  }
});

test('going back to the link step on a map without links does not break the tour', async ({ atlas }) => {
  await atlas.goto(pathToFileURL(NO_LINKS_PAGE).href);
  await expect(card(atlas)).toBeVisible();
  await toSwitchStep(atlas, 'Plain');
  await card(atlas).getByRole('button', { name: 'Show Plain' }).click();
  await expect(card(atlas)).toContainText('5 of 5');
  // back past the switch step to the link step, now on a map that has no links: the fixture fails on any page error
  await card(atlas).getByRole('button', { name: 'Back' }).click();
  await expect(card(atlas)).toContainText('4 of 5');
  await card(atlas).getByRole('button', { name: 'Back' }).click();
  await expect(card(atlas)).toContainText('Click a link');
  await atlas.waitForTimeout(1000); // a few frames of the tour following its target
  await expect(card(atlas)).toBeVisible();
});
