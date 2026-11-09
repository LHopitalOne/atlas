function routeTemplate(req) {
  if (!req.route) return req.path;
  const path = `${req.baseUrl}${req.route.path}`.replace(/(.)\/$/, '$1');
  return path.replace(/:(\w+)/g, '{$1}');
}

function recvLog(req, res, next) {
  res.on('finish', () => {
    console.log(`RECV http ${req.method} ${routeTemplate(req)}`);
  });
  next();
}

module.exports = recvLog;
