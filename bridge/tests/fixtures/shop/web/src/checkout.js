// Checkout page logic.
import { placeOrder, loadOrder } from './api.js';

export async function checkout(cart) {
  const order = await placeOrder(cart.items);
  return loadOrder(order.id);
}
