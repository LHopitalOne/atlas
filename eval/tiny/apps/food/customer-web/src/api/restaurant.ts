import { config } from "../config";
import type { Menu, NewOrder, Order } from "./types";

const { baseUrl, endpoints } = config.restaurant;

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`restaurant API ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

export async function fetchMenu(restaurantId: number): Promise<Menu> {
  const res = await fetch(`${baseUrl}${endpoints.menu}/${restaurantId}`);
  return json<Menu>(res);
}

export async function placeOrder(order: NewOrder): Promise<Order> {
  const res = await fetch(`${baseUrl}${endpoints.orders}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(order),
  });
  return json<Order>(res);
}

export async function getOrder(orderId: number): Promise<Order> {
  const res = await fetch(`${baseUrl}${endpoints.orders}/${orderId}`);
  return json<Order>(res);
}
