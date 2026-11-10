import type { FastifyPluginAsync } from 'fastify';

import { lookupBin } from '../clients/bins.ts';
import { fetchBalance } from '../clients/ledger.ts';
import { createPayment, refundPayment } from '../clients/provider.ts';
import { orders, type Order } from '../orders.ts';
import { session } from '../session.ts';

interface CreateOrderBody {
  card_number: string;
  amount_cents: number;
}

export const apiRoutes: FastifyPluginAsync = async (app) => {
  app.post<{ Body: CreateOrderBody }>('/orders', async (request, reply) => {
    console.log(`RECV L09 http POST /api/orders amount=${request.body.amount_cents}`);
    const card = await lookupBin(request.body.card_number);
    const order = orders.create(request.body.amount_cents, card);
    const payment = await createPayment(session.merchantId, order.amountCents, order.id);
    orders.update(order, { paymentId: payment.id, status: payment.status });
    return reply.code(201).send(order);
  });

  app.post<{ Params: { orderId: string } }>('/orders/:orderId/refund', async (request, reply) => {
    console.log(`RECV L10 http POST /api/orders/${request.params.orderId}/refund`);
    const order = orders.get(request.params.orderId);
    if (!order?.paymentId) {
      return reply.code(404).send({ error: 'unknown order' });
    }
    const refund = await refundPayment(order.paymentId);
    return reply.code(202).send(refund);
  });

  app.get<{ Params: { orderId: string } }>('/orders/:orderId/events', (request, reply) => {
    const order = orders.get(request.params.orderId);
    if (!order) {
      return reply.code(404).send({ error: 'unknown order' });
    }
    console.log(`RECV L08 sse GET /api/orders/${order.id}/events`);
    reply.hijack();
    reply.raw.writeHead(200, {
      'content-type': 'text/event-stream',
      'cache-control': 'no-cache',
      connection: 'keep-alive',
      'access-control-allow-origin': '*',
    });
    const push = (current: Order) => {
      reply.raw.write(`event: status\nid: ${Date.now()}\ndata: ${JSON.stringify(current)}\n\n`);
    };
    push(order);
    orders.on(`order:${order.id}`, push);
    request.raw.on('close', () => orders.off(`order:${order.id}`, push));
  });

  app.get('/balance', async () => {
    console.log('RECV L11 http GET /api/balance');
    return fetchBalance(session.merchantId);
  });
};
