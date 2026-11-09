const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const config = require('../config');

const packageDefinition = protoLoader.loadSync(config.inventory.protoPath, {
  keepCase: false,
  longs: Number,
  enums: String,
  defaults: true,
  oneofs: true,
});
const { inventory } = grpc.loadPackageDefinition(packageDefinition);

class InventoryClient {
  constructor(target = config.inventory.target) {
    this.stub = new inventory.v1.InventoryService(target, grpc.credentials.createInsecure());
  }

  reserve(sku, quantity, orderId) {
    return this.unary('Reserve', { sku, quantity, orderId });
  }

  release(reservationId) {
    return this.unary('Release', { reservationId });
  }

  getStock(sku) {
    return this.unary('GetStock', { sku });
  }

  unary(method, request) {
    const deadline = new Date(Date.now() + config.inventory.deadlineMs);
    return new Promise((resolve, reject) => {
      this.stub[method](request, { deadline }, (err, response) => {
        if (err) return reject(err);
        return resolve(response);
      });
    });
  }

  close() {
    this.stub.close();
  }
}

const inventoryClient = new InventoryClient();

module.exports = { InventoryClient, inventoryClient };
