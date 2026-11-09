const config = require('./config');

function requestLog(req, res, next) {
  res.on('finish', () => {
    const route = req.route ? req.baseUrl + (req.route.path === '/' ? '' : req.route.path) : req.path;
    console.log(`RECV http ${req.method} ${route || '/'}`);
  });
  next();
}

function cors(req, res, next) {
  res.set('Access-Control-Allow-Origin', config.corsOrigin);
  res.set('Access-Control-Allow-Headers', 'Content-Type');
  res.set('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
}

function errorHandler(err, req, res, _next) {
  console.error(err);
  res.status(502).json({ error: 'upstream failure' });
}

module.exports = { requestLog, cors, errorHandler };
