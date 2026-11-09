import { ChatApi } from '../web/dist/api.js';
import { ChatSocket } from '../web/dist/socket.js';

const api = new ChatApi();
const alice = new ChatSocket('alice');

function waitFor(socket, predicate, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`timeout waiting for ${label}`)), 5000);
    const off = socket.onFrame((frame) => {
      if (predicate(frame)) {
        clearTimeout(timer);
        off();
        resolve(frame);
      }
    });
  });
}

const rooms = await api.listRooms();
console.log('smoke: rooms', rooms.map((r) => r.name).join(','));
const room = await api.createRoom('smoke-test');

await alice.connect();
alice.join(room.id);
await new Promise((r) => setTimeout(r, 100));

const delivered = waitFor(alice, (f) => f.type === 'message' && f.message.text.includes('hello'), 'broadcast');
alice.say(room.id, 'hello, heck of a day');
console.log('smoke: broadcast', (await delivered).message.text);

const rejected = waitFor(alice, (f) => f.type === 'rejected', 'rejection');
alice.say(room.id, 'join my crypto giveaway');
console.log('smoke: rejected', (await rejected).reason);

const viaRest = waitFor(alice, (f) => f.type === 'message' && f.message.author === 'bob', 'rest broadcast');
await api.postMessage(room.id, 'bob', 'posted over REST');
await viaRest;

const history = await api.getHistory(room.id);
console.log('smoke: history', history.length);

const ticket = await api.reportUser('alice', 'bob', room.id, 'spam');
console.log('smoke: ticket', ticket.ticketId, ticket.openReports);

alice.close();
console.log('smoke: ok');
