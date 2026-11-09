import { annotate, getSeries, getSummary, health, listMetrics } from "./api/metrics.js";
import { config } from "./config.js";
import { notifySlack } from "./notify.js";
import { panel } from "./render.js";

const LOAD_ALERT_THRESHOLD = Number(process.env.LOAD_ALERT_THRESHOLD ?? 8);

async function refresh(): Promise<void> {
  const names = (await listMetrics()).slice(0, config.maxPanels);
  const lines: string[] = [];
  for (const name of names) {
    const [summary, series] = await Promise.all([getSummary(name), getSeries(name)]);
    lines.push(panel(summary, series));
    if (name === "system.load.1" && summary.last > LOAD_ALERT_THRESHOLD) {
      await notifySlack(`load is ${summary.last.toFixed(2)}`);
    }
  }
  console.log(`--- ${new Date().toISOString()} (${config.collectorUrl}) ---`);
  console.log(lines.join("\n") || "(no metrics yet)");
}

async function main(): Promise<void> {
  const once = process.argv.includes("--once");
  if (!(await health())) throw new Error("collector unhealthy");
  await annotate("dashboard session started");

  await refresh();
  if (once) return;
  setInterval(() => refresh().catch((err) => console.error("refresh failed:", err.message)), config.refreshMs);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
