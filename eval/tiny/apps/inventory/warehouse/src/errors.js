const { status } = require('@grpc/grpc-js');

const GRPC_TO_HTTP = {
  [status.NOT_FOUND]: 404,
  [status.FAILED_PRECONDITION]: 409,
  [status.INVALID_ARGUMENT]: 400,
  [status.DEADLINE_EXCEEDED]: 504,
  [status.UNAVAILABLE]: 503,
};

function errorHandler(err, req, res, next) {
  const httpStatus = GRPC_TO_HTTP[err.code] || 500;
  if (httpStatus >= 500) console.error(err);
  res.status(httpStatus).json({ error: err.details || err.message });
}

module.exports = errorHandler;
