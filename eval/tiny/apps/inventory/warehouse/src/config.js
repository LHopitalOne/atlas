const path = require('path');

module.exports = {
  host: process.env.HOST || '127.0.0.1',
  port: parseInt(process.env.PORT || '41975', 10),
  inventory: {
    target: process.env.INVENTORY_GRPC_TARGET || '127.0.0.1:41974',
    protoPath: path.join(__dirname, '..', 'proto', 'inventory.proto'),
    deadlineMs: parseInt(process.env.INVENTORY_DEADLINE_MS || '3000', 10),
  },
};
