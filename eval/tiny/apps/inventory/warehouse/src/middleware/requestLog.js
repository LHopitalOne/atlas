function routeTemplate(req) {
  if (!req.route) return req.originalUrl.split('?')[0];
  const sub = req.route.path === '/' ? '' : req.route.path;
  return (req.baseUrl + sub || '/').replace(/:(\w+)/g, '{$1}');
}

function requestLog(req, res, next) {
  res.on('finish', () => {
    console.log(`RECV http ${req.method} ${routeTemplate(req)} -> ${res.statusCode}`);
  });
  next();
}

module.exports = requestLog;
