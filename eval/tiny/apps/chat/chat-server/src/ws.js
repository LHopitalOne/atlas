const { WebSocketServer } = require('ws');
const hub = require('./hub');
const { postMessage, MessageRejected } = require('./messages');

function attachChatSocket(server) {
  const wss = new WebSocketServer({ server, path: '/ws' });

  wss.on('connection', (socket, req) => {
    console.log('RECV websocket CONNECT /ws');
    const params = new URL(req.url, 'http://localhost').searchParams;
    const user = params.get('user') || 'anonymous';

    socket.on('message', async (raw) => {
      console.log('RECV websocket SEND /ws');
      let frame;
      try {
        frame = JSON.parse(raw.toString());
      } catch {
        return hub.send(socket, { type: 'error', error: 'invalid json' });
      }

      if (frame.type === 'join') {
        hub.join(frame.roomId, socket);
        return;
      }
      if (frame.type === 'message') {
        try {
          await postMessage(frame.roomId, user, frame.text);
        } catch (err) {
          const reason = err instanceof MessageRejected ? err.message : 'delivery failed';
          hub.send(socket, { type: 'rejected', clientId: frame.clientId, reason });
        }
      }
    });

    socket.on('close', () => hub.leave(socket));
  });

  return wss;
}

module.exports = { attachChatSocket };
