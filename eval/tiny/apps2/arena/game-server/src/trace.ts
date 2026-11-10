// Test instrumentation: maps an observed inbound interaction to its link id.
const LINK_IDS: Record<string, string> = {
  'join:player-web': 'A01',
  'answer:player-web': 'A02',
  'join:quiz-bot': 'A05',
  'answer:quiz-bot': 'A06',
  'POST /admin/questions': 'H01',
  'GET /api/leaderboard': 'H02',
};

export function traceRecv(key: string, detail = ''): void {
  const id = LINK_IDS[key] ?? 'UNKNOWN';
  console.log(`RECV ${id} game-server ${key} ${detail}`.trim());
}
