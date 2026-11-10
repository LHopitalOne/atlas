function intFromEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  return raw ? Number.parseInt(raw, 10) : fallback;
}

export const config = {
  port: intFromEnv('PORT', 44010),
  scorekeeper: {
    baseUrl: process.env.SCOREKEEPER_URL ?? 'http://127.0.0.1:44021',
    udpHost: process.env.SCOREKEEPER_UDP_HOST ?? '127.0.0.1',
    udpPort: intFromEnv('SCOREKEEPER_UDP_PORT', 44020),
  },
  game: {
    minPlayers: intFromEnv('MIN_PLAYERS', 2),
    roundTimeoutMs: intFromEnv('ROUND_TIMEOUT_MS', 4000),
    pointsPerCorrect: 10,
  },
} as const;
