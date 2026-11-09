const { WebSocketServer } = require('ws');
const store = require('../store');

class DriverHub {
  constructor() {
    this.sockets = new Map();
    this.wss = null;
  }

  attach(server, path) {
    this.path = path;
    this.wss = new WebSocketServer({ server, path });
    this.wss.on('connection', (socket, req) => this.onConnection(socket, req));
  }

  onConnection(socket, req) {
    const url = new URL(req.url, 'http://localhost');
    const driverId = url.searchParams.get('driverId');
    console.log(`RECV websocket CONNECT ${this.path}`);
    if (!driverId) {
      socket.close(4400, 'driverId required');
      return;
    }

    this.sockets.set(driverId, socket);
    store.upsertDriver(driverId, { status: 'connected' });

    socket.on('message', (raw) => this.onMessage(driverId, raw));
    socket.on('close', () => {
      this.sockets.delete(driverId);
      store.upsertDriver(driverId, { status: 'offline' });
    });
  }

  onMessage(driverId, raw) {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    console.log(`RECV websocket SEND ${this.path}`);
    if (msg.type === 'status') {
      store.upsertDriver(driverId, { status: msg.status });
    }
  }

  availableDriverId() {
    for (const driverId of this.sockets.keys()) {
      if (store.getDriver(driverId)?.status === 'available') return driverId;
    }
    return null;
  }

  notify(driverId, payload) {
    const socket = this.sockets.get(driverId);
    if (!socket || socket.readyState !== socket.OPEN) return false;
    socket.send(JSON.stringify(payload));
    return true;
  }
}

module.exports = new DriverHub();
