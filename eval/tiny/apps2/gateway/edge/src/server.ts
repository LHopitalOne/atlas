import express, { type NextFunction, type Request, type Response } from 'express';

import { config } from './config.js';
import { ordersProxy, usersProxy } from './proxies.js';
import { dashboardRouter } from './routes/dashboard.js';

const app = express();

app.disable('x-powered-by');

// Proxies go first so request bodies are streamed upstream untouched.
app.use(usersProxy);
app.use(ordersProxy);

app.use(express.json());
app.use('/api/dashboard', dashboardRouter);

app.get('/healthz', (_req, res) => {
  res.json({ ok: true });
});

app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('edge error:', err.message);
  res.status(502).json({ error: 'bad gateway' });
});

app.listen(config.port, '127.0.0.1', () => {
  console.log(`edge listening on http://127.0.0.1:${config.port}`);
});
