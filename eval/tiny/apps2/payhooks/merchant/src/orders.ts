import { EventEmitter } from 'node:events';
import { randomUUID } from 'node:crypto';

import type { CardInfo } from './clients/bins.ts';

export interface Order {
  id: string;
  paymentId: string | null;
  amountCents: number;
  status: string;
  refundedCents: number;
  card: CardInfo;
}

class OrderBook extends EventEmitter {
  private readonly orders = new Map<string, Order>();

  create(amountCents: number, card: CardInfo): Order {
    const order: Order = { id: `ord_${randomUUID().slice(0, 8)}`, paymentId: null, amountCents, status: 'created', refundedCents: 0, card };
    this.orders.set(order.id, order);
    return order;
  }

  get(id: string): Order | undefined {
    return this.orders.get(id);
  }

  byPayment(paymentId: string): Order | undefined {
    return [...this.orders.values()].find((order) => order.paymentId === paymentId);
  }

  update(order: Order, changes: Partial<Order>): void {
    Object.assign(order, changes);
    this.emit(`order:${order.id}`, order);
  }
}

export const orders = new OrderBook();
