import { test as base, expect } from '@playwright/test';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

export const PAGE = pathToFileURL(resolve('dist/atlas-offline.html')).href;

/** A page with Atlas loaded, failing the test on any uncaught error. */
export const test = base.extend({
  atlas: async ({ page }, use) => {
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.open = async (hash = '') => {
      await page.goto(PAGE + hash);
      await expect(page.locator('#count')).toContainText('nodes');
      await page.waitForTimeout(600);
    };
    await use(page);
    expect(errors, 'uncaught errors').toEqual([]);
  },
});
export { expect };
