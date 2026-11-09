import { ChatApi, avatarUrl } from './api.js';
import { ChatSocket } from './socket.js';
import type { Message } from './types.js';

const api = new ChatApi();
const user = localStorage.getItem('chat.user') ?? `guest-${Math.floor(Math.random() * 1000)}`;
const socket = new ChatSocket(user);

const roomsEl = document.querySelector<HTMLUListElement>('#rooms')!;
const messagesEl = document.querySelector<HTMLOListElement>('#messages')!;
const composer = document.querySelector<HTMLFormElement>('#composer')!;
const newRoom = document.querySelector<HTMLFormElement>('#new-room')!;
let currentRoom = '';

function renderMessage(message: Message): void {
  const li = document.createElement('li');
  li.innerHTML = `<img src="${avatarUrl(message.author)}" width="20" /> <b></b> <span></span> <button>report</button>`;
  li.querySelector('b')!.textContent = message.author;
  li.querySelector('span')!.textContent = message.text;
  li.querySelector('button')!.onclick = () => api.reportUser(user, message.author, message.roomId, 'abusive');
  messagesEl.append(li);
}

async function openRoom(roomId: string): Promise<void> {
  currentRoom = roomId;
  messagesEl.replaceChildren();
  (await api.getHistory(roomId)).forEach(renderMessage);
  socket.join(roomId);
}

async function loadRooms(): Promise<void> {
  const rooms = await api.listRooms();
  roomsEl.replaceChildren(
    ...rooms.map((room) => {
      const li = document.createElement('li');
      li.textContent = `# ${room.name}`;
      li.onclick = () => openRoom(room.id);
      return li;
    }),
  );
  if (!currentRoom && rooms.length) await openRoom(rooms[0].id);
}

socket.onFrame((frame) => {
  if (frame.type === 'message' && frame.message.roomId === currentRoom) renderMessage(frame.message);
  if (frame.type === 'rejected') alert(`Message blocked: ${frame.reason}`);
});

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const input = composer.elements.namedItem('text') as HTMLInputElement;
  if (input.value.trim()) socket.say(currentRoom, input.value.trim());
  input.value = '';
});

newRoom.addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = newRoom.elements.namedItem('name') as HTMLInputElement;
  const room = await api.createRoom(input.value);
  input.value = '';
  await loadRooms();
  await openRoom(room.id);
});

await socket.connect();
await loadRooms();
