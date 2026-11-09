const express = require('express');
const upstream = require('../upstream');

const router = express.Router();

router.post('/', async (req, res, next) => {
  try {
    const order = await upstream.createOrder({
      customer_email: req.body.email,
      items: req.body.items,
    });
    res.status(201).json(order);
  } catch (err) {
    next(err);
  }
});

router.get('/:id', async (req, res, next) => {
  try {
    res.json(await upstream.getOrder(req.params.id));
  } catch (err) {
    next(err);
  }
});

module.exports = router;
