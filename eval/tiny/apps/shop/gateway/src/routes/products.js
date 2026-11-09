const express = require('express');
const upstream = require('../upstream');

const router = express.Router();

router.get('/', async (req, res, next) => {
  try {
    const inStock = req.query.in_stock === 'true';
    res.json(await upstream.listProducts(inStock ? { in_stock: true } : {}));
  } catch (err) {
    next(err);
  }
});

router.get('/:id', async (req, res, next) => {
  try {
    res.json(await upstream.getProduct(req.params.id));
  } catch (err) {
    next(err);
  }
});

module.exports = router;
