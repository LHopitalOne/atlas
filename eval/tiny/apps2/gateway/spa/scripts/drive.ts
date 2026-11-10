// Smoke driver for run.sh: exercises the real SPA api module from Node (a browser would use
// the same functions), then plays the browser's part for the third-party URLs in index.html.
import { readFile } from 'node:fs/promises';

import {
  getDashboard,
  getOrder,
  getOrderItems,
  getUser,
  getWishlist,
  http,
  listOrders,
  listUsers,
  placeOrder,
  registerUser,
} from '../src/api';

const gateway = process.env.GATEWAY_ORIGIN ?? 'http://127.0.0.1:43010';
// In the browser '/api' resolves against the page origin; Node needs an absolute origin.
http.defaults.baseURL = `${gateway}/api`;

async function main(): Promise<void> {
  const users = await listUsers();
  const ada = await getUser(users[0].id);
  const newcomer = await registerUser('Grace', 'grace@bazaarly.test');
  const wishlist = await getWishlist(ada.id);
  console.log(`users=${users.length} first=${ada.name} new=${newcomer.id} wishlist=${wishlist.length}`);

  const order = await placeOrder(ada.id, [{ sku: 'SKU-101', qty: 2, price_usd: 12.5 }], 'EUR');
  const mine = await listOrders(ada.id);
  const again = await getOrder(order.id);
  const items = await getOrderItems(order.id);
  console.log(`order=${again.id} total=${order.total} ${order.currency} mine=${mine.length} items=${items.length}`);

  const dash = await getDashboard(ada.id);
  console.log(`dashboard orders=${dash.stats.orderCount}`);

  const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
  const scriptSrc = /<script src="(https:[^"]+)"/.exec(html)?.[1];
  const anchorHref = /<a href="(https:[^"]+)"/.exec(html)?.[1];
  const external = [
    ['O02', 'GET', scriptSrc],
    ['O03', 'LINK', anchorHref],
  ] as const;
  for (const [id, op, url] of external) {
    if (!url) throw new Error(`no ${op} url in index.html`);
    const res = await fetch(url, { redirect: 'follow' });
    const u = new URL(url);
    console.log(`RECV ${id} ${op} ${u.host} ${u.pathname} status=${res.status}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
