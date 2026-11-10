import { http } from './client';
import type { LineItem, Order } from './types';

const ORDERS = '/orders';

export async function listOrders(buyer?: number): Promise<Order[]> {
  const { data } = await http.get<Order[]>(ORDERS, { params: buyer ? { buyer } : undefined });
  return data;
}

export async function placeOrder(buyerId: number, items: LineItem[], currency = 'USD'): Promise<Order> {
  const { data } = await http.post<Order>(ORDERS, { buyer_id: buyerId, items, currency });
  return data;
}

export async function getOrder(id: number): Promise<Order> {
  const { data } = await http.get<Order>(`${ORDERS}/${id}`);
  return data;
}

export async function getOrderItems(id: number): Promise<LineItem[]> {
  const { data } = await http.get<LineItem[]>(`${ORDERS}/${id}/items`);
  return data;
}
