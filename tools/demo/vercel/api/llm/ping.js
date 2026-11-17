// GET /api/llm/ping: says whether this deployment holds an OpenRouter key (see lib/llm-proxy.js).
import { ping } from '../../lib/llm-proxy.js';

export function GET(request) {
  return ping(request);
}
