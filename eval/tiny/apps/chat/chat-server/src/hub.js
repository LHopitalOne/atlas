const { WebSocket } = require('ws');

const members = new Map();

function join(roomId, socket) {
  if (!members.has(roomId)) members.set(roomId, new Set());
  members.get(roomId).add(socket);
}

function leave(socket) {
  for (const sockets of members.values()) sockets.delete(socket);
}

function send(socket, payload) {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}

function broadcast(roomId, payload) {
  for (const socket of members.get(roomId) || []) {
    send(socket, payload);
  }
}

module.exports = { join, leave, send, broadcast };
