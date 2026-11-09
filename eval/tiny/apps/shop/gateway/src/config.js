module.exports = {
  port: Number(process.env.GATEWAY_PORT || 41000),
  host: process.env.GATEWAY_HOST || '127.0.0.1',
  catalogUrl: process.env.CATALOG_URL || 'http://127.0.0.1:41001',
  ordersUrl: process.env.ORDERS_URL || 'http://127.0.0.1:41002',
  upstreamTimeoutMs: Number(process.env.UPSTREAM_TIMEOUT_MS || 5000),
};
