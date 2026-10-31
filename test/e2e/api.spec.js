import { test, expect } from './fixtures.js';

test('Atlas.loadGraph shows a graph passed at runtime', async ({ atlas }) => {
  await atlas.open();
  await atlas.evaluate(() =>
    window.Atlas.loadGraph({
      meta: { label: 'Shop', status: ['Matched', 'Ambiguous', 'Unmatched', 'Inferred'] },
      repos: [
        {
          name: 'web',
          domains: [
            {
              name: 'checkout',
              services: [{ name: 'cart_api', leaves: [{ name: 'POST /cart', kind: 1 }] }, { name: 'pay_api' }],
            },
          ],
        },
        { name: 'core', domains: [{ name: 'billing', services: [{ name: 'ledger' }] }] },
      ],
      edges: [
        [3, 1, 0],
        [1, 2, 1],
      ],
    }),
  );
  await expect(atlas.locator('#count')).toContainText('4');
  await expect(atlas.locator('#scale [data-v="self"]')).toHaveText('Shop');
  await atlas.keyboard.press('/');
  await atlas.keyboard.type('ledger');
  await expect(atlas.locator('#results')).toContainText('ledger');
});

test('Atlas.loadGraph rejects a malformed graph with a readable error', async ({ atlas }) => {
  await atlas.open();
  const msg = await atlas.evaluate(() => {
    try {
      window.Atlas.loadGraph({ repos: [], edges: [[0, 5, 9]] });
      return 'accepted';
    } catch (e) {
      return e.message;
    }
  });
  expect(msg).toContain('Invalid graph spec');
  expect(msg).toContain('status 9');
});
