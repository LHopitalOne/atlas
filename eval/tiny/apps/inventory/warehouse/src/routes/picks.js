const express = require('express');
const { inventoryClient } = require('../clients/inventoryClient');

const router = express.Router();

router.post('/', async (req, res, next) => {
  const { sku, quantity, orderId } = req.body || {};
  if (!sku || !Number.isInteger(quantity) || quantity <= 0) {
    return res.status(400).json({ error: 'sku and a positive integer quantity are required' });
  }
  try {
    const reservation = await inventoryClient.reserve(sku, quantity, orderId || '');
    return res.status(201).json({
      pickId: reservation.reservationId,
      sku,
      quantity,
      available: reservation.available,
    });
  } catch (err) {
    return next(err);
  }
});

router.delete('/:pickId', async (req, res, next) => {
  try {
    const result = await inventoryClient.release(req.params.pickId);
    res.json(result);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
