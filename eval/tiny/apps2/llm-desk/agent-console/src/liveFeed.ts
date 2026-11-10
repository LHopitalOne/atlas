import { EventEmitter } from 'node:events';

import type { DeskEvent } from './types.ts';

/**
 * Subscribes to desk's Server-Sent Events endpoint using fetch streaming
 * and re-emits each SSE message as a typed event.
 */
export class LiveFeed extends EventEmitter {
  private readonly abort = new AbortController();

  constructor(
    private readonly url: URL,
    private readonly agent: string,
  ) {
    super();
  }

  async open(): Promise<void> {
    const res = await fetch(this.url, {
      headers: { accept: 'text/event-stream', 'x-agent': this.agent },
      signal: this.abort.signal,
    });
    if (!res.ok || !res.body) {
      throw new Error(`event stream ${this.url} -> ${res.status}`);
    }
    void this.pump(res.body).catch((err: unknown) => {
      if (!this.abort.signal.aborted) this.emit('error', err);
    });
  }

  close(): void {
    this.abort.abort();
  }

  private async pump(body: ReadableStream<Uint8Array>): Promise<void> {
    const decoder = new TextDecoder();
    let buffer = '';
    for await (const chunk of body) {
      buffer += decoder.decode(chunk, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const message = parseMessage(raw);
        if (message) this.emit(message.event, message);
      }
    }
  }
}

function parseMessage(raw: string): DeskEvent | null {
  let event = 'message';
  let id: string | undefined;
  const data: string[] = [];
  for (const line of raw.split('\n')) {
    if (line.startsWith(':')) continue;
    const idx = line.indexOf(':');
    const field = idx === -1 ? line : line.slice(0, idx);
    const value = idx === -1 ? '' : line.slice(idx + 1).trimStart();
    if (field === 'event') event = value;
    else if (field === 'id') id = value;
    else if (field === 'data') data.push(value);
  }
  if (data.length === 0) return null;
  return { id, event, data: JSON.parse(data.join('\n')) };
}
