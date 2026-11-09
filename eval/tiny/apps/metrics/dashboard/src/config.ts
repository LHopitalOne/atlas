export const config = {
  collectorUrl: process.env.COLLECTOR_URL ?? "http://127.0.0.1:41712",
  refreshMs: Number(process.env.DASHBOARD_REFRESH_MS ?? 5000),
  maxPanels: Number(process.env.DASHBOARD_MAX_PANELS ?? 6),
  slackWebhookUrl: process.env.SLACK_WEBHOOK_URL,
};
