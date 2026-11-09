const express = require('express');
const { inventoryClient } = require('../clients/inventoryClient');

const router = express.Router();

router.get('/:sku', async (req, res, next) => {
  try {
    const level = await inventoryClient.getStock(req.params.sku);
    res.json(level);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
