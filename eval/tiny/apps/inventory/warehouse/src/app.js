const express = require('express');
const requestLog = require('./middleware/requestLog');
const errorHandler = require('./errors');
const stockRoutes = require('./routes/stock');
const pickRoutes = require('./routes/picks');
const restockOrderRoutes = require('./routes/restockOrders');

const app = express();

app.use(express.json());
app.use(requestLog);

app.get('/healthz', (req, res) => res.json({ ok: true }));
app.use('/stock', stockRoutes);
app.use('/picks', pickRoutes);
app.use('/restock-orders', restockOrderRoutes);

app.use(errorHandler);

module.exports = app;
