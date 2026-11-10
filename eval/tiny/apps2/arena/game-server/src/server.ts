import { createServer } from 'node:http';
import express from 'express';
import { Server } from 'socket.io';
import { ScorekeeperClient } from './clients/scorekeeper.js';
import { config } from './config.js';
import { registerQuizNamespace } from './game/namespace.js';
import { QuestionBank } from './game/question-bank.js';
import { adminRouter } from './routes/admin.js';
import { leaderboardRouter } from './routes/leaderboard.js';
import { ScoreReporter } from './scoring/udp-reporter.js';

const bank = new QuestionBank();
const reporter = new ScoreReporter(config.scorekeeper.udpHost, config.scorekeeper.udpPort);
const scorekeeper = new ScorekeeperClient(config.scorekeeper.baseUrl);

const app = express();
app.use(express.json());
app.use((_req, res, next) => {
  res.setHeader('access-control-allow-origin', '*');
  next();
});
app.get('/healthz', (_req, res) => {
  res.json({ ok: true });
});
app.use('/admin', adminRouter(bank));
app.use('/api', leaderboardRouter(scorekeeper));

const httpServer = createServer(app);
const io = new Server(httpServer, { cors: { origin: '*' } });
registerQuizNamespace(io, bank, reporter);

httpServer.listen(config.port, () => {
  console.log(`game-server listening on :${config.port}`);
});

function shutdown(): void {
  io.close();
  reporter.close();
  httpServer.close(() => process.exit(0));
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
