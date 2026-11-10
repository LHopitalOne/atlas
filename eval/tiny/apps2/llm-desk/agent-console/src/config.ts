export const config = {
  deskUrl: process.env.DESK_URL ?? 'http://localhost:42000',
  agent: process.env.AGENT_NAME ?? process.env.USER ?? 'agent',
  triageTimeoutMs: Number(process.env.TRIAGE_TIMEOUT_MS ?? 90_000),
};
