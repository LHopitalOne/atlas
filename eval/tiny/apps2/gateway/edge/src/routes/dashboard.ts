import { Router } from 'express';

import { fetchOrdersForBuyer, fetchUser } from '../upstreams.js';

export const dashboardRouter = Router();

// Aggregation endpoint: one round trip for the SPA instead of two.
dashboardRouter.get('/:userId', async (req, res, next) => {
  console.log(`RECV L09 GET ${req.originalUrl}`);
  try {
    const [user, orders] = await Promise.all([
      fetchUser(req.params.userId),
      fetchOrdersForBuyer(req.params.userId),
    ]);
    const spentUsd = orders.filter((o) => o.currency === 'USD').reduce((sum, o) => sum + o.total, 0);
    res.json({ user, orders, stats: { orderCount: orders.length, spentUsd } });
  } catch (err) {
    next(err);
  }
});
