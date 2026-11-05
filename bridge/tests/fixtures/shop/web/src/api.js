// Calls the orders API.
const BASE = process.env.API_URL || 'http://api:8000';

export async function placeOrder(items) {
  const res = await fetch(`${BASE}/orders`, { method: 'POST', body: JSON.stringify({ items }) });
  return res.json();
}

export async function loadOrder(id) {
  return (await fetch(`${BASE}/orders/${id}`)).json();
}

export async function loadUser(id) {
  return (await fetch(`${BASE}/users/${id}`)).json();
}
