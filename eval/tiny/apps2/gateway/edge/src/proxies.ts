import type { Request, Response } from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

import { config } from './config.js';

// /api/users/** -> users service, with the /api prefix stripped (/api/users/7 -> /users/7)
export const usersProxy = createProxyMiddleware<Request, Response>({
  target: config.usersUrl,
  pathFilter: '/api/users',
  pathRewrite: { '^/api': '' },
  changeOrigin: true,
  xfwd: true,
});

// /api/orders/** -> orders service, which serves its API under /v1 (/api/orders/3 -> /v1/orders/3)
export const ordersProxy = createProxyMiddleware<Request, Response>({
  target: config.ordersUrl,
  pathFilter: (path) => path.startsWith('/api/orders'),
  pathRewrite: (path) => path.replace(/^\/api\/orders/, '/v1/orders'),
  changeOrigin: true,
  xfwd: true,
});
