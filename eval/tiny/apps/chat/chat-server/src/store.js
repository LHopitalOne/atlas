const crypto = require('crypto');

const rooms = new Map();

function listRooms() {
  return [...rooms.values()].map(({ id, name, createdAt }) => ({ id, name, createdAt }));
}

function createRoom(name) {
  const room = { id: crypto.randomUUID().slice(0, 8), name, createdAt: new Date().toISOString(), messages: [] };
  rooms.set(room.id, room);
  return room;
}

function getRoom(id) {
  return rooms.get(id);
}

function addMessage(roomId, author, text) {
  const room = rooms.get(roomId);
  const message = { id: crypto.randomUUID(), roomId, author, text, sentAt: new Date().toISOString() };
  room.messages.push(message);
  return message;
}

function history(roomId, limit = 50) {
  const room = rooms.get(roomId);
  return room ? room.messages.slice(-limit) : [];
}

createRoom('lobby');

module.exports = { listRooms, createRoom, getRoom, addMessage, history };
