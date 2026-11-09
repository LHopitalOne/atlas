import { WS_URL } from './config.js';
import type { ServerFrame } from './types.js';

type Listener = (frame: ServerFrame) => void;

export class ChatSocket {
  private ws?: WebSocket;
  private listeners = new Set<Listener>();
  private seq = 0;

  constructor(private user: string, private url: string = WS_URL) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${this.url}?user=${encodeURIComponent(this.user)}`);
      this.ws.addEventListener('open', () => resolve(), { once: true });
      this.ws.addEventListener('error', () => reject(new Error('websocket error')), { once: true });
      this.ws.addEventListener('message', (event) => {
        console.log('RECV websocket SEND /ws');
        const frame = JSON.parse(String(event.data)) as ServerFrame;
        this.listeners.forEach((listener) => listener(frame));
      });
    });
  }

  onFrame(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(frame: Record<string, unknown>): void {
    this.ws?.send(JSON.stringify(frame));
  }

  join(roomId: string): void {
    this.emit({ type: 'join', roomId });
  }

  say(roomId: string, text: string): string {
    const clientId = `${this.user}-${++this.seq}`;
    this.emit({ type: 'message', roomId, text, clientId });
    return clientId;
  }

  close(): void {
    this.ws?.close();
  }
}
