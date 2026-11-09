const store = require('./store');
const moderation = require('./moderationClient');
const hub = require('./hub');

class MessageRejected extends Error {
  constructor(reason) {
    super(reason);
    this.name = 'MessageRejected';
  }
}

async function postMessage(roomId, author, text) {
  if (!store.getRoom(roomId)) {
    throw new Error(`unknown room ${roomId}`);
  }
  const verdict = await moderation.checkMessage({ roomId, author, text });
  if (!verdict.allowed) {
    throw new MessageRejected(verdict.reason);
  }
  const message = store.addMessage(roomId, author, verdict.sanitizedText || text);
  hub.broadcast(roomId, { type: 'message', message });
  return message;
}

module.exports = { postMessage, MessageRejected };
