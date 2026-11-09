const http = require('http');
const config = require('./config');
const app = require('./app');
const hub = require('./realtime/driverHub');

const server = http.createServer(app);
hub.attach(server, config.driverStreamPath);

server.listen(config.port, config.host, () => {
  console.log(`dispatch listening on http://${config.host}:${config.port}`);
});

process.on('SIGTERM', () => server.close(() => process.exit(0)));
