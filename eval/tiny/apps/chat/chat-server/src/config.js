const path = require('path');

module.exports = {
  host: process.env.HOST || '127.0.0.1',
  port: Number(process.env.PORT || 41310),
  moderationAddr: process.env.MODERATION_ADDR || '127.0.0.1:41311',
  moderationTimeoutMs: Number(process.env.MODERATION_TIMEOUT_MS || 2000),
  protoPath: path.join(__dirname, '..', 'proto', 'moderation.proto'),
  corsOrigin: process.env.CORS_ORIGIN || '*',
};
