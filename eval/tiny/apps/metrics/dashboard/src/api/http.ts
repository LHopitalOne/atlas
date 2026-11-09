import axios from "axios";
import { config } from "../config.js";

export const http = axios.create({
  baseURL: config.collectorUrl,
  timeout: 5000,
  headers: { "User-Agent": "metrics-dashboard/0.1" },
});
