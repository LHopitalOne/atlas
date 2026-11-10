import { configure, getBalance, placeOrder, refundOrder, watchOrder, type Order } from './api.js';

const form = document.querySelector<HTMLFormElement>('#checkout')!;
const statusList = document.querySelector<HTMLUListElement>('#orders')!;
const balanceOut = document.querySelector<HTMLOutputElement>('#balance')!;

configure({ merchantUrl: document.body.dataset.merchantUrl ?? window.location.origin });

function render(order: Order): void {
  let row = statusList.querySelector<HTMLLIElement>(`[data-order="${order.id}"]`);
  if (!row) {
    row = document.createElement('li');
    row.dataset.order = order.id;
    const refund = document.createElement('button');
    refund.textContent = 'Refund';
    refund.addEventListener('click', () => void refundOrder(order.id));
    row.append(document.createElement('span'), refund);
    statusList.prepend(row);
  }
  row.querySelector('span')!.textContent = `${order.id} ${order.status} (${order.card.scheme ?? 'unknown card'})`;
  void getBalance().then((balance) => {
    balanceOut.value = (balance.balance_cents / 100).toFixed(2);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  const order = await placeOrder(String(data.get('card')), Math.round(Number(data.get('amount')) * 100));
  render(order);
  watchOrder(order.id, render);
});
