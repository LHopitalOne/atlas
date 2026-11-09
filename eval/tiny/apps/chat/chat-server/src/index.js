const http = require('http');
const express = require('express');
const config = require('./config');
const rooms = require('./routes/rooms');
const reports = require('./routes/reports');
const { attachChatSocket } = require('./ws');
const { requestLog, cors, errorHandler } = require('./middleware');

const app = express();
app.use(cors);
app.use(express.json());
app.use(requestLog);

app.get('/healthz', (req, res) => res.json({ ok: true }));
app.use('/api/rooms', rooms);
app.use('/api/reports', reports);
app.use(errorHandler);

const server = http.createServer(app);
attachChatSocket(server);

server.listen(config.port, config.host, () => {
  console.log(`chat-server listening on http://${config.host}:${config.port}`);
});
