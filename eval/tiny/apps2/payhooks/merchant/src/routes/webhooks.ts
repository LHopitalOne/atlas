import { createHmac, timingSafeEqual } from 'node:crypto';

import type { FastifyPluginAsync } from 'fastify';

import { orders } from '../orders.ts';
import { session } from '../session.ts';

interface WebhookEvent {
  id: string;
  type: 'payment.settled' | 'payment.refunded';
  data: { payment_id: string; status: string; refunded_cents: number };
}

function verify(header: string | undefined, rawBody: string, secret: string): boolean {
  if (!header) return false;
  const parts = Object.fromEntries(header.split(',').map((part) => part.split('=') as [string, string]));
  const expected = createHmac('sha256', secret).update(`${parts.t}.${rawBody}`).digest('hex');
  const given = parts.v1 ?? '';
  return given.length === expected.length && timingSafeEqual(Buffer.from(given), Buffer.from(expected));
}

export const webhookRoutes: FastifyPluginAsync = async (app) => {
  app.addContentTypeParser('application/json', { parseAs: 'string' }, (_request, body, done) => done(null, body));

  app.post('/payhooks', async (request, reply) => {
    const rawBody = request.body as string;
    if (!verify(request.headers['payhooks-signature'] as string | undefined, rawBody, session.signingSecret)) {
      return reply.code(400).send({ error: 'bad signature' });
    }
    const event = JSON.parse(rawBody) as WebhookEvent;
    console.log(`RECV L04 http POST /webhooks/payhooks type=${event.type} payment=${event.data.payment_id}`);
    const order = orders.byPayment(event.data.payment_id);
    if (order) {
      orders.update(order, { status: event.data.status, refundedCents: event.data.refunded_cents });
    }
    return reply.code(204).send();
  });
};
