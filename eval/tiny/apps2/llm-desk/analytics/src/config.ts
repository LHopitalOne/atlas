import { hostname } from 'node:os';

export interface AnalyticsConfig {
  redisUrl: string;
  stream: string;
  group: string;
  consumer: string;
  reportUrl: string;
  flushIntervalMs: number;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): AnalyticsConfig {
  return {
    redisUrl: env.REDIS_URL ?? 'redis://localhost:6379/0',
    stream: env.TRIAGED_STREAM ?? 'desk.tickets.triaged',
    group: env.CONSUMER_GROUP ?? 'analytics',
    consumer: env.CONSUMER_NAME ?? `analytics-${hostname()}-${process.pid}`,
    reportUrl: env.REPORT_URL ?? 'https://httpbin.org/post',
    flushIntervalMs: Number(env.FLUSH_INTERVAL_MS ?? 60_000),
  };
}
