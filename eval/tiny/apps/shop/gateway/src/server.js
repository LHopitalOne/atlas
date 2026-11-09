const app = require('./app');
const config = require('./config');

app.listen(config.port, config.host, () => {
  console.log(`gateway listening on ${config.host}:${config.port}`);
});
