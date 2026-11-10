import { config } from '../config.ts';

export interface Registration {
  id: string;
  signing_secret: string;
}

export interface ProviderPayment {
  id: string;
  status: string;
}

class ProviderError extends Error {
  constructor(public readonly status: number, body: string) {
    super(`provider responded ${status}: ${body}`);
  }
}

async function providerPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(new URL(path, config.providerUrl), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ProviderError(response.status, await response.text());
  }
  return (await response.json()) as T;
}

export function registerWebhook(webhookUrl: string): Promise<Registration> {
  return providerPost<Registration>('/v1/merchants', {
    name: config.merchantName,
    webhook_url: webhookUrl,
  });
}

export function createPayment(merchantId: string, amountCents: number, reference: string): Promise<ProviderPayment> {
  return providerPost<ProviderPayment>('/v1/payments', {
    merchant_id: merchantId,
    amount_cents: amountCents,
    currency: 'EUR',
    reference,
  });
}

export function refundPayment(paymentId: string, amountCents?: number) {
  return providerPost<{ payment_id: string; amount_cents: number }>(
    `/v1/payments/${encodeURIComponent(paymentId)}/refunds`,
    { amount_cents: amountCents ?? null },
  );
}
