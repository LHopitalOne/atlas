export interface Order {
  id: string;
  paymentId: string | null;
  amountCents: number;
  status: string;
  refundedCents: number;
  card: { bin: string; scheme: string | null; country: string | null; source: string };
}

export interface Balance {
  merchant_id: string;
  settled_cents: number;
  refunded_cents: number;
  balance_cents: number;
}

let merchantBase = '';

export function configure(options: { merchantUrl: string }): void {
  merchantBase = options.merchantUrl.replace(/\/+$/, '');
}

function apiUrl(path: string): string {
  return `${merchantBase}/api${path}`;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`merchant responded ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function placeOrder(cardNumber: string, amountCents: number): Promise<Order> {
  const response = await fetch(apiUrl('/orders'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ card_number: cardNumber, amount_cents: amountCents }),
  });
  return json<Order>(response);
}

export async function refundOrder(orderId: string): Promise<{ payment_id: string; amount_cents: number }> {
  const response = await fetch(apiUrl(`/orders/${encodeURIComponent(orderId)}/refund`), { method: 'POST' });
  return json(response);
}

export async function getBalance(): Promise<Balance> {
  return json<Balance>(await fetch(apiUrl('/balance')));
}

export function watchOrder(orderId: string, onStatus: (order: Order) => void): () => void {
  const source = new EventSource(apiUrl(`/orders/${encodeURIComponent(orderId)}/events`));
  source.addEventListener('status', (event) => {
    onStatus(JSON.parse((event as MessageEvent<string>).data) as Order);
  });
  return () => source.close();
}
