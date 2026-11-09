const crypto = require('crypto');
const express = require('express');

const router = express.Router();
const orders = [];

router.post('/', (req, res) => {
  const { sku, quantity, reason } = req.body || {};
  if (!sku || !Number.isInteger(quantity) || quantity <= 0) {
    return res.status(400).json({ error: 'sku and a positive integer quantity are required' });
  }
  const order = {
    id: crypto.randomUUID(),
    sku,
    quantity,
    reason: reason || null,
    status: 'placed',
    createdAt: new Date().toISOString(),
  };
  orders.push(order);
  return res.status(201).json(order);
});

router.get('/', (req, res) => {
  res.json(orders);
});

module.exports = router;
