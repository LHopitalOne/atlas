import { Redis } from 'ioredis';

import type { AnalyticsConfig } from './config.ts';
import { parseFields, type TriagedEntry } from './counts.ts';

type StreamReply = [stream: string, entries: [id: string, fields: string[]][]][] | null;

/** Reads triaged tickets from the desk's Redis stream as a member of a consumer group. */
export class TriagedStreamConsumer {
  private readonly redis: Redis;
  private running = false;

  constructor(private readonly cfg: AnalyticsConfig) {
    this.redis = new Redis(cfg.redisUrl, { maxRetriesPerRequest: null, lazyConnect: true });
  }

  async start(onEntry: (entry: TriagedEntry, id: string) => void): Promise<void> {
    await this.redis.connect();
    await this.ensureGroup();
    this.running = true;
    while (this.running) {
      let reply: StreamReply;
      try {
        reply = (await this.redis.xreadgroup(
          'GROUP', this.cfg.group, this.cfg.consumer,
          'COUNT', 100,
          'BLOCK', 2000,
          'STREAMS', this.cfg.stream, '>',
        )) as StreamReply;
      } catch (err) {
        if (!this.running) return;
        throw err;
      }
      if (!reply) continue;
      for (const [, entries] of reply) {
        for (const [id, fields] of entries) {
          onEntry(parseFields(fields), id);
          await this.redis.xack(this.cfg.stream, this.cfg.group, id);
        }
      }
    }
  }

  async stop(): Promise<void> {
    this.running = false;
    this.redis.disconnect();
  }

  private async ensureGroup(): Promise<void> {
    try {
      await this.redis.xgroup('CREATE', this.cfg.stream, this.cfg.group, '0', 'MKSTREAM');
    } catch (err) {
      if (!(err instanceof Error) || !err.message.includes('BUSYGROUP')) throw err;
    }
  }
}
