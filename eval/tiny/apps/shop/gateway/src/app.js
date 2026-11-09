const express = require('express');
const products = require('./routes/products');
const orders = require('./routes/orders');

const app = express();
app.use(express.json());

app.use('/api/products', products);
app.use('/api/orders', orders);

// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  if (err.response) {
    res.status(err.response.status).json(err.response.data);
    return;
  }
  console.error(err);
  res.status(502).json({ error: 'upstream unavailable' });
});

module.exports = app;
