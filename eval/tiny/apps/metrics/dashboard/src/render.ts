import type { Series, Summary } from "./api/types.js";

const BARS = "▁▂▃▄▅▆▇█";

export function sparkline(series: Series): string {
  const values = series.points.map((p) => p.value);
  if (values.length === 0) return "";
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  return values.map((v) => BARS[Math.round(((v - min) / span) * (BARS.length - 1))]).join("");
}

export function panel(summary: Summary, series: Series): string {
  const fmt = (n: number) => n.toFixed(2).padStart(9);
  return `${summary.name.padEnd(28)} last${fmt(summary.last)} min${fmt(summary.min)} max${fmt(summary.max)}  ${sparkline(series)}`;
}
