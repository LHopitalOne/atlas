import axios from "axios";
import { config } from "./config.js";

export async function notifySlack(message: string): Promise<void> {
  if (!config.slackWebhookUrl) return;
  await axios.post(config.slackWebhookUrl, { text: message });
}
