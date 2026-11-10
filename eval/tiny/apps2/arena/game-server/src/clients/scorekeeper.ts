export interface ScoreEntry {
  player: string;
  points: number;
}

export class ScorekeeperClient {
  constructor(private readonly baseUrl: string) {}

  async fetchScores(): Promise<ScoreEntry[]> {
    const res = await fetch(`${this.baseUrl}/scores`, {
      headers: { accept: 'application/json' },
      signal: AbortSignal.timeout(2000),
    });
    if (!res.ok) {
      throw new Error(`scorekeeper responded ${res.status}`);
    }
    return (await res.json()) as ScoreEntry[];
  }
}
