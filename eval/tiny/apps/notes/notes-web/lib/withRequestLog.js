export function withRequestLog(route, handler) {
  return async function loggedHandler(req, res) {
    console.log(`RECV http ${req.method} ${route}`);
    return handler(req, res);
  };
}
