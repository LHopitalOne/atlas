const env = import.meta.env ?? {};

export const API_URL: string = env.VITE_API_URL ?? 'http://127.0.0.1:41310';
export const WS_URL: string = env.VITE_WS_URL ?? 'ws://127.0.0.1:41310/ws';
