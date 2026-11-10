import { getDashboard, getOrderItems, getWishlist, listUsers, placeOrder } from './api';

declare const dayjs: (input?: string | number | Date) => { format(fmt: string): string };

const CURRENT_USER = 1;

async function renderDashboard(): Promise<void> {
  const el = document.querySelector<HTMLElement>('#dashboard')!;
  const { user, stats } = await getDashboard(CURRENT_USER);
  const wishlist = await getWishlist(CURRENT_USER);
  el.innerHTML = `
    <h2>Hi ${user.name}</h2>
    <p>${stats.orderCount} orders, ${stats.spentUsd.toFixed(2)} USD spent, as of ${dayjs().format('MMM D, HH:mm')}</p>
    <p>Wishlist: ${wishlist.map((w) => w.sku).join(', ') || 'empty'}</p>`;
}

async function renderUsers(): Promise<void> {
  const el = document.querySelector<HTMLElement>('#users')!;
  const users = await listUsers();
  el.innerHTML = `<ul>${users.map((u) => `<li>${u.name}${u.verified ? ' (verified)' : ''}</li>`).join('')}</ul>`;
}

document.querySelector<HTMLFormElement>('#checkout')!.addEventListener('submit', async (event) => {
  event.preventDefault();
  const order = await placeOrder(CURRENT_USER, [{ sku: 'SKU-101', qty: 1, price_usd: 25 }], 'EUR');
  const items = await getOrderItems(order.id);
  alert(`Order #${order.id}: ${items.length} item(s), ${order.total} ${order.currency}`);
  await renderDashboard();
});

void Promise.all([renderDashboard(), renderUsers()]);
