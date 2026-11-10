import type { DailyCount } from './counts.ts';

/** Ships daily counts to the reporting endpoint (an echo service in this deployment). */
export class CountsReporter {
  constructor(
    private readonly endpoint: string,
    private readonly source = 'llm-desk/analytics',
  ) {}

  async report(counts: DailyCount[]): Promise<void> {
    const res = await fetch(this.endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ source: this.source, generated_at: new Date().toISOString(), counts }),
      signal: AbortSignal.timeout(20_000),
    });
    if (!res.ok) throw new Error(`report POST ${this.endpoint} -> ${res.status}`);
    const echo = (await res.json()) as { json?: { counts?: unknown[] } };
    console.log(`RECV O3 POST ${new URL(this.endpoint).host}/post rows=${echo.json?.counts?.length ?? 0}`);
  }
}
