const env: Partial<ImportMetaEnv> = import.meta.env ?? {};

export const API_URL = (env.VITE_API_URL ?? "http://127.0.0.1:41810").replace(/\/$/, "");
