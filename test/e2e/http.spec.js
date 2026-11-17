// HTTP links between repositories: the links panel with accuracy, a link's proof (both lines of code, GitHub links,
// proof badge, SCIP checks), an endpoint's callers and impact, and builds with embedded maps.
// test/fixtures/http-shop.json is written by bridge/tests/test_atlas_http.py.
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { test, expect } from './fixtures.js';

const SPEC = JSON.parse(readFileSync('test/fixtures/http-shop.json', 'utf8'));
const MAPS_PAGE = resolve('dist/test-maps.html');

async function openShop(atlas) {
  await atlas.open();
  await atlas.evaluate(spec => window.Atlas.loadGraph(spec), SPEC);
  await expect(atlas.locator('#links')).toBeVisible();
}

test('the links panel shows the accuracy, every link by direction, and requests with no route', async ({ atlas }) => {
  await openShop(atlas);
  const panel = atlas.locator('#links');
  await expect(panel.locator('h2')).toHaveText('HTTP links');
  await expect(panel.locator('.acc-s').first()).toContainText('2/2');
  await expect(panel.locator('.acc-s').nth(1)).toContainText('0');
  await expect(panel).toContainText('web → api');
  await expect(panel.locator('[data-link]')).toHaveCount(2);
  await expect(panel.locator('[data-link]').first()).toContainText('Confirmed by SCIP');
  await expect(panel.locator('.unmatched')).toContainText('GET /users/{id}');
  await expect(atlas.locator('#linksBtn')).toBeVisible();
  await atlas.keyboard.press('Escape');
  // the Key lists the links in the line styles the map draws them, and their protocols
  const key = atlas.locator('#legendBody');
  await expect(key).toContainText('Links between services');
  await expect(key).toContainText('Confirmed by SCIP');
  await expect(key.locator('.lg-note')).toHaveText(/^HTTP \d+$/);
  await expect(key).toContainText('HTTP endpoint');
  await expect(panel).toBeHidden();
  await atlas.locator('#ov').focus();
  await atlas.keyboard.press('l');
  await expect(panel).toBeVisible();
});

test('the panel close button keeps its size and sits beside the title, however long the subtitle', async ({
  atlas,
}) => {
  await openShop(atlas);
  await atlas.setViewportSize({ width: 420, height: 860 }); // narrow: the subtitle wraps over several lines
  const btn = await atlas.locator('#links [data-lclose]').boundingBox();
  const title = await atlas.locator('#linksTitle').boundingBox();
  expect(btn.width).toBe(32);
  expect(Math.abs(btn.y + btn.height / 2 - (title.y + title.height / 2))).toBeLessThan(2);
});

test('the Key shows one section at a time and keeps one height, below the toolbar', async ({ atlas }) => {
  await atlas.setViewportSize({ width: 1280, height: 640 });
  await openShop(atlas);
  await atlas.keyboard.press('Escape'); // the links panel
  await atlas.locator('#legend').evaluate(d => (d.open = true));
  const tabs = atlas.locator('#legendBody .lg-tabs [role="radio"]');
  await expect(tabs).toHaveText(['Links', 'Code', 'Repos']);
  await expect(tabs.first()).toHaveAttribute('aria-checked', 'true');
  const heights = [];
  for (const [i, shown] of [
    [1, 'code'],
    [2, 'repos'],
    [0, 'links'],
  ]) {
    await tabs.nth(i).click();
    await expect(atlas.locator(`#legendBody .lg-pane[data-pane="${shown}"]`)).toBeVisible();
    await expect(atlas.locator('#legendBody .lg-pane:not([hidden])')).toHaveCount(1);
    heights.push((await atlas.locator('#legend').boundingBox()).height);
  }
  expect(new Set(heights).size).toBe(1);
  const key = await atlas.locator('#legend').boundingBox();
  const bar = await atlas.locator('.toolbar').boundingBox();
  expect(key.y).toBeGreaterThan(bar.y + bar.height);
  // arrow keys move between sections, as on the map switcher
  await tabs.first().focus();
  await atlas.keyboard.press('ArrowRight');
  await expect(tabs.nth(1)).toBeFocused();
  await expect(tabs.nth(1)).toHaveAttribute('aria-checked', 'true');
});

test('a link opens its proof: the line that sends it, the route that serves it, GitHub links', async ({ atlas }) => {
  await openShop(atlas);
  await atlas.locator('#links [data-link]').first().click();
  const insp = atlas.locator('#insp');
  await expect(insp.locator('#insTitle')).toHaveText('POST /orders');
  await expect(insp.locator('.kindrow')).toContainText('Confirmed by SCIP');
  const sites = insp.locator('.site');
  await expect(sites.first()).toContainText('Sends the request');
  await expect(sites.first()).toContainText('src/api.js:5');
  await expect(sites.first().locator('.pl.hit')).toContainText('fetch(`${BASE}/orders`');
  await expect(sites.first().locator('a')).toHaveAttribute(
    'href',
    'https://github.com/example/shop-web/blob/2222222222222222222222222222222222222222/src/api.js#L5',
  );
  await expect(sites.nth(1)).toContainText('Serves it');
  await expect(sites.nth(1)).toContainText('handled by post_order');
  await expect(sites.nth(1).locator('a')).toHaveAttribute('href', /shop-api\/blob\/1{40}\/app\/main\.py#L10$/);
  await expect(insp.locator('.checks')).toContainText('BASE');
  await expect(insp.locator('.checks')).toContainText('confirmed');
  await insp.locator('[data-close]').click();
  await expect(atlas.locator('#app')).not.toHaveClass(/has-insp/);
});

test('an endpoint lists its callers in other repositories and shows its impact on the map', async ({ atlas }) => {
  await openShop(atlas);
  await atlas.locator('#links [data-link]').nth(1).click();
  const insp = atlas.locator('#insp');
  await expect(insp.locator('.kindrow')).toContainText('Inferred');
  await insp.locator('.row[data-id]').nth(1).click();
  await expect(insp.locator('#insTitle')).toHaveText('GET /orders/{order_id}');
  await expect(insp).toContainText('HTTP endpoint');
  await expect(insp).toContainText('Called over HTTP from');
  await expect(insp.locator('[data-link]')).toContainText('loadOrder');
  const impact = insp.locator('[data-http-impact]');
  await expect(insp).toContainText('1 call site in 1 other repository');
  await impact.click();
  await expect(impact).toHaveAttribute('aria-pressed', 'true');
  await expect(impact).toHaveText('Hide on map');
  await impact.click();
  await expect(impact).toHaveAttribute('aria-pressed', 'false');
});

test('what calls a repository lights up from the links panel', async ({ atlas }) => {
  await openShop(atlas);
  const row = atlas.locator('#links .imp-row');
  await expect(row).toHaveCount(1);
  await expect(row).toContainText('api');
  await expect(row).toContainText('2 endpoints, 2 call sites in web');
  await row.locator('button').click();
  await expect(row.locator('button')).toHaveAttribute('aria-pressed', 'true');
});

test.describe('a build with embedded maps', () => {
  test.beforeAll(() => {
    const maps = `shop:test/fixtures/http-shop.json:Shop,graphify:test/fixtures/graphify-shop.json:Plain`;
    execFileSync('node', ['scripts/build.mjs', '--offline', `--maps=${maps}`, `--out=${MAPS_PAGE}`]);
  });

  test('offers its maps, opens the first, and switches by button and by hash', async ({ atlas }) => {
    await atlas.goto(pathToFileURL(MAPS_PAGE).href);
    await expect(atlas.locator('#count')).toContainText('nodes');
    await expect(atlas.locator('#scale [role="radio"]')).toHaveText(['Shop', 'Plain']);
    await expect(atlas.locator('#links')).toBeVisible();
    await expect(atlas).toHaveURL(/#shop$/);
    await atlas.locator('#scale [data-v="graphify"]').click();
    await expect(atlas).toHaveURL(/#graphify/);
    await expect(atlas.locator('#links')).toBeHidden();
    await expect(atlas.locator('#linksBtn')).toBeHidden();
    await atlas.goto(pathToFileURL(MAPS_PAGE).href + '#nosuchmap');
    await expect(atlas.locator('#scale [data-v="shop"]')).toHaveAttribute('aria-checked', 'true');
  });
});

test.describe('a build that keeps its maps in their own files', () => {
  const page = resolve('dist/test-external/index.html');
  let server, base;
  test.beforeAll(async () => {
    const maps = `shop:test/fixtures/http-shop.json:Shop,graphify:test/fixtures/graphify-shop.json:Plain`;
    execFileSync('node', ['scripts/build.mjs', '--offline', `--maps=${maps}`, '--external-maps', `--out=${page}`]);
    // a browser fetches files beside a page only over http, so serve the folder (a missing map answers 404)
    server = createServer((req, res) => {
      try {
        res.end(readFileSync(join(dirname(page), new URL(req.url, 'http://x').pathname.slice(1) || 'index.html')));
      } catch {
        res.writeHead(404).end();
      }
    });
    await new Promise(done => server.listen(0, '127.0.0.1', done));
    base = `http://127.0.0.1:${server.address().port}/`;
  });
  test.afterAll(() => server.close());

  test('downloads the first map, then each other map when it is chosen', async ({ atlas }) => {
    const asked = [];
    atlas.on('request', r => r.url().includes('/maps/') && asked.push(new URL(r.url()).pathname));
    await atlas.goto(base);
    await expect(atlas.locator('#count')).toContainText('nodes');
    await expect(atlas.locator('#links')).toBeVisible();
    expect(asked).toEqual(['/maps/shop.json']);
    await atlas.locator('#scale [data-v="graphify"]').click();
    await expect(atlas).toHaveURL(/#graphify/);
    await expect(atlas.locator('#links')).toBeHidden();
    await atlas.locator('#scale [data-v="shop"]').click();
    await expect(atlas.locator('#links')).toBeVisible();
    expect(asked).toEqual(['/maps/shop.json', '/maps/graphify.json']);
  });

  test('a map that cannot be downloaded says so', async ({ atlas }) => {
    await atlas.route('**/maps/graphify.json', r => r.fulfill({ status: 404, body: '' }));
    await atlas.goto(base);
    await expect(atlas.locator('#count')).toContainText('nodes');
    await atlas.locator('#scale [data-v="graphify"]').click();
    await expect(atlas.locator('.toast')).toContainText('Could not download Plain (404');
  });
});
