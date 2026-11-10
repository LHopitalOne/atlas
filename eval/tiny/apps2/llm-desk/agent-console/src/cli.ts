#!/usr/bin/env -S npx tsx
import { config } from './config.ts';
import { DeskClient } from './deskClient.ts';
import { LiveFeed } from './liveFeed.ts';
import { runShift } from './shift.ts';

const USAGE = `usage: agent-console <command>
  queue [team]            list open tickets, optionally for one team
  show <id>               show one ticket
  reply <id> [text]       reply (drafted by the desk when no text is given)
  close <id>              close a ticket
  watch                   print live desk events
  shift <inbox.json>      file an inbox and work the most urgent ticket`;

async function main(argv: string[]): Promise<void> {
  const [command, ...args] = argv;
  const desk = new DeskClient(config.deskUrl, config.agent);

  switch (command) {
    case 'queue':
      for (const t of await desk.listTickets({ team: args[0] })) {
        console.log(`${t.id}\t${t.status}\t${t.team ?? '-'}\t${t.urgent ? 'URGENT' : ''}\t${t.subject}`);
      }
      return;
    case 'show':
      console.log(JSON.stringify(await desk.getTicket(args[0]), null, 2));
      return;
    case 'reply': {
      const text = args.slice(1).join(' ');
      const ticket = await desk.reply(args[0], text ? { body: text } : { useDraft: true });
      console.log(ticket.replies.at(-1));
      return;
    }
    case 'close':
      await desk.setStatus(args[0], 'closed');
      return;
    case 'watch': {
      const feed = new LiveFeed(desk.eventsUrl(), desk.agentName);
      for (const name of ['ticket.triaged', 'ticket.answered', 'ticket.status']) {
        feed.on(name, (msg) => console.log(name, JSON.stringify(msg.data)));
      }
      process.once('SIGINT', () => feed.close());
      await feed.open();
      return;
    }
    case 'shift':
      await runShift(desk, args[0] ?? 'fixtures/tickets.json', config.triageTimeoutMs);
      return;
    default:
      console.error(USAGE);
      process.exitCode = 2;
  }
}

main(process.argv.slice(2)).catch((err: unknown) => {
  console.error(err instanceof Error ? err.message : err);
  process.exitCode = 1;
});
