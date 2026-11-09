const app = require('./app');
const config = require('./config');
const { inventoryClient } = require('./clients/inventoryClient');

const server = app.listen(config.port, config.host, () => {
  console.log(`warehouse listening on http://${config.host}:${config.port}`);
});

function shutdown() {
  server.close(() => {
    inventoryClient.close();
    process.exit(0);
  });
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
