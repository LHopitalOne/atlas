import { readFile } from 'node:fs/promises';

import { DeskClient } from './deskClient.ts';
import { LiveFeed } from './liveFeed.ts';
import type { DeskEvent, NewTicket, Ticket } from './types.ts';

/** Collects ticket.triaged events from the moment it is created, so fast triage is never missed. */
class TriageWatcher {
  private readonly seen = new Map<string, Ticket>();
  private wake: () => void = () => {};

  constructor(private readonly feed: LiveFeed) {
    feed.on('ticket.triaged', this.onTriaged);
  }

  private readonly onTriaged = (msg: DeskEvent<Ticket>) => {
    this.seen.set(msg.data.id, msg.data);
    console.log(`  triaged ${msg.data.id} -> ${msg.data.team}${msg.data.urgent ? ' [URGENT]' : ''}`);
    this.wake();
  };

  async waitFor(ids: string[], timeoutMs: number): Promise<Ticket[]> {
    const deadline = Date.now() + timeoutMs;
    try {
      while (!ids.every((id) => this.seen.has(id))) {
        const left = deadline - Date.now();
        if (left <= 0) throw new Error(`timed out waiting for triage of ${ids.join(', ')}`);
        await new Promise<void>((resolve) => {
          const timer = setTimeout(resolve, left);
          this.wake = () => {
            clearTimeout(timer);
            resolve();
          };
        });
      }
      return ids.map((id) => this.seen.get(id)!);
    } finally {
      this.feed.off('ticket.triaged', this.onTriaged);
    }
  }
}

/** A scripted agent shift: file the inbox, wait for triage, answer the most urgent ticket. */
export async function runShift(desk: DeskClient, inboxPath: string, timeoutMs: number): Promise<void> {
  const inbox = JSON.parse(await readFile(inboxPath, 'utf8')) as NewTicket[];

  const feed = new LiveFeed(desk.eventsUrl(), desk.agentName);
  feed.on('ticket.answered', (msg: DeskEvent<{ id: string; reply: string }>) =>
    console.log(`  answered ${msg.data.id}: ${msg.data.reply.slice(0, 80)}...`),
  );
  await feed.open();

  try {
    console.log(`filing ${inbox.length} tickets`);
    const watcher = new TriageWatcher(feed);
    const filed: string[] = [];
    for (const item of inbox) {
      const ticket = await desk.createTicket(item);
      filed.push(ticket.id);
    }
    await watcher.waitFor(filed, timeoutMs);

    const urgent = await desk.listTickets({ urgent: true });
    const queue = urgent.length > 0 ? urgent : await desk.listTickets();
    console.log(`queue: ${queue.map((t) => `${t.id}(${t.team})`).join(' ')}`);

    const top = await desk.getTicket(queue[0].id);
    console.log(`working ${top.id}: ${top.subject}`);
    await desk.reply(top.id, { useDraft: true });
    const closed = await desk.setStatus(top.id, 'closed');
    console.log(`closed ${closed.id} with ${closed.replies.length} reply`);
  } finally {
    feed.close();
  }
}
