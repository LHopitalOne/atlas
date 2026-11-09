const express = require('express');
const recvLog = require('./middleware/recvLog');
const ridesRouter = require('./routes/rides');
const driversRouter = require('./routes/drivers');

const app = express();
app.use(express.json());
app.use(recvLog);

app.get('/healthz', (req, res) => res.json({ ok: true }));
app.use('/rides', ridesRouter);
app.use('/drivers', driversRouter);

module.exports = app;
