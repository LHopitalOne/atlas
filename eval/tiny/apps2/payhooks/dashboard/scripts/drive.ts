// Node driver for the dashboard: runs the same api module the browser uses.
import { readFile } from 'node:fs/promises';

import { EventSource } from 'eventsource';

import { configure, getBalance, placeOrder, refundOrder, watchOrder, type Order } from '../src/api.ts';

Object.assign(globalThis, { EventSource });

configure({ merchantUrl: process.env.MERCHANT_URL ?? 'http://127.0.0.1:46020' });

function waitForStatus(orderId: string, wanted: string, timeoutMs = 20000): Promise<Order> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      stop();
      reject(new Error(`timed out waiting for ${orderId} to become ${wanted}`));
    }, timeoutMs);
    const stop = watchOrder(orderId, (order) => {
      console.log(`dashboard: ${order.id} is ${order.status}`);
      if (order.status === wanted) {
        clearTimeout(timer);
        stop();
        resolve(order);
      }
    });
  });
}

async function checkout(cardNumber: string, amountCents: number, refund: boolean): Promise<void> {
  const order = await placeOrder(cardNumber, amountCents);
  console.log(`dashboard: placed ${order.id} card=${JSON.stringify(order.card)}`);
  await waitForStatus(order.id, 'settled');
  if (refund) {
    const refunded = waitForStatus(order.id, 'refunded');
    await refundOrder(order.id);
    await refunded;
  }
}

async function followStatusLink(): Promise<void> {
  const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
  const href = /<a href="(https:\/\/[^"]+)">status page<\/a>/.exec(html)?.[1];
  if (!href) throw new Error('status link missing from index.html');
  const response = await fetch(href, { method: 'HEAD' });
  console.log(`RECV L14 outside LINK ${new URL(href).host}${new URL(href).pathname} status=${response.status}`);
}

await checkout('4571 7360 1234 5678', 1250, true);
await checkout('0000 0000 0000 0000', 990, false);

await new Promise((resolve) => setTimeout(resolve, 1500));
const balance = await getBalance();
console.log(`dashboard: balance ${JSON.stringify(balance)}`);
if (balance.settled_cents !== 2240 || balance.refunded_cents !== 1250) {
  throw new Error('ledger balance does not match the orders placed');
}
await followStatusLink();
