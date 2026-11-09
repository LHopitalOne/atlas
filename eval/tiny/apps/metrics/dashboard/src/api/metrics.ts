import { http } from "./http.js";
import type { Series, Summary } from "./types.js";

export async function health(): Promise<boolean> {
  const res = await http.get<{ status: string }>("/healthz");
  return res.data.status === "ok";
}

export async function listMetrics(): Promise<string[]> {
  const { data } = await http.get<{ metrics: string[] }>("/api/metrics");
  return data.metrics;
}

export async function getSeries(name: string, limit = 30): Promise<Series> {
  const { data } = await http.get<Series>(`/api/metrics/${encodeURIComponent(name)}`, { params: { limit } });
  return data;
}

export async function getSummary(name: string): Promise<Summary> {
  const { data } = await http.get<Summary>(`/api/metrics/${encodeURIComponent(name)}/summary`);
  return data;
}

export async function annotate(text: string): Promise<void> {
  await http.post("/api/annotations", { text, ts: Date.now() / 1000, author: "dashboard" });
}
