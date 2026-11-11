import { test, expect } from './fixtures.js';
import { readFileSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

// A map `atlas map` wrote carries the OpenRouter key in #askKey (bridge/atlas_bridge/adapters/page/page.py):
// Ask Atlas then asks the model straight from the file; written without a key, Ask is off.
test.use({ contextOptions: { reducedMotion: 'reduce' } });

const SLOT = '<script type="application/json" id="askKey"></script>';

function writtenPage(key) {
  const html = readFileSync(resolve('dist/atlas-offline.html'), 'utf-8');
  if (!html.includes(SLOT)) throw new Error('dist/atlas-offline.html has no key slot: run npm run build');
  const file = join(mkdtempSync(join(tmpdir(), 'atlas-written-')), 'atlas.html');
  writeFileSync(
    file,
    html.replace(SLOT, `<script type="application/json" id="askKey">${JSON.stringify({ key })}</script>`),
  );
  return pathToFileURL(file).href;
}

async function openPage(page, url) {
  await page.goto(url);
  await expect(page.locator('#count')).toContainText('nodes');
  await page.waitForTimeout(600);
}

test('a map written without a key has Ask Atlas turned off', async ({ atlas }) => {
  await openPage(atlas, writtenPage(null));
  await atlas.keyboard.press('a');
  await expect(atlas.locator('#toast')).toContainText('Ask Atlas is off');
  await expect(atlas.locator('#ask')).not.toHaveClass(/on/);
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('routeSearch');
  await expect(atlas.locator('#results [role="option"]').first()).toBeVisible();
  await expect(atlas.locator('#results')).not.toContainText('Ask Atlas');
});

test('a map written with a key asks the model on OpenRouter with it', async ({ atlas }) => {
  const sent = [];
  await atlas.route('https://openrouter.ai/**', async route => {
    const r = route.request();
    if (r.method() === 'POST') sent.push(r.headers()['authorization']);
    await route.fulfill({
      status: 200,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': '*',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ choices: [{ message: { role: 'assistant', content: 'Answered by the model.' } }] }),
    });
  });
  await openPage(atlas, writtenPage('sk-or-test'));
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('What is this codebase?');
  await expect(atlas.locator('#results [role="option"]').first()).toContainText('Ask Atlas');
  await atlas.keyboard.press('Enter');
  await expect(atlas.locator('#ask .ans-text')).toContainText('Answered by the model.');
  await expect(atlas.locator('#ask .ask-mode')).toHaveText('meta/muse-ember');
  await expect(atlas.locator('#ask .keybar')).toBeHidden();
  expect(sent).toContain('Bearer sk-or-test');
});
