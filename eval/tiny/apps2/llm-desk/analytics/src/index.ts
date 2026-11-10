import { loadConfig } from './config.ts';
import { TriagedStreamConsumer } from './consumer.ts';
import { DailyCounts } from './counts.ts';
import { CountsReporter } from './reporter.ts';

const cfg = loadConfig();
const counts = new DailyCounts();
const reporter = new CountsReporter(cfg.reportUrl);
const consumer = new TriagedStreamConsumer(cfg);

async function flush(): Promise<void> {
  if (!counts.hasChanges) return;
  try {
    await reporter.report(counts.snapshot());
  } catch (err) {
    console.error('report failed:', err instanceof Error ? err.message : err);
  }
}

const timer = setInterval(() => void flush(), cfg.flushIntervalMs);

async function shutdown(): Promise<void> {
  clearInterval(timer);
  await flush();
  await consumer.stop();
  process.exit(0);
}
process.once('SIGTERM', () => void shutdown());
process.once('SIGINT', () => void shutdown());

console.log(`analytics consuming ${cfg.stream} as ${cfg.group}/${cfg.consumer}`);
await consumer.start((entry, id) => {
  console.log(`RECV R1 XREADGROUP ${cfg.stream} id=${id} ticket=${entry.ticketId} team=${entry.team}`);
  counts.add(entry);
});
