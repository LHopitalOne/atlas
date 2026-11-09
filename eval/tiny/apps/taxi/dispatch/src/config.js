const config = {
  host: process.env.DISPATCH_HOST || '127.0.0.1',
  port: Number(process.env.DISPATCH_PORT || 41200),
  driverStreamPath: process.env.DRIVER_STREAM_PATH || '/drivers/stream',
  offerTimeoutMs: Number(process.env.OFFER_TIMEOUT_MS || 15000),
};

module.exports = config;
