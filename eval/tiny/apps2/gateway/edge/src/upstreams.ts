import { config } from './config.js';

export interface UpstreamUser {
  id: number;
  name: string;
  email: string;
  verified: boolean;
}

export interface UpstreamOrder {
  id: number;
  buyer_id: number;
  currency: string;
  total: number;
}

async function getJson<T>(url: URL | string): Promise<T> {
  const res = await fetch(url, { headers: { accept: 'application/json' } });
  if (!res.ok) {
    throw new Error(`upstream ${url} answered ${res.status}`);
  }
  return (await res.json()) as T;
}

export function fetchUser(userId: string): Promise<UpstreamUser> {
  return getJson<UpstreamUser>(new URL(`/users/${encodeURIComponent(userId)}`, config.usersUrl));
}

export function fetchOrdersForBuyer(userId: string): Promise<UpstreamOrder[]> {
  const qs = new URLSearchParams({ buyer: userId });
  return getJson<UpstreamOrder[]>(`${config.ordersUrl}/v1/orders?${qs}`);
}
