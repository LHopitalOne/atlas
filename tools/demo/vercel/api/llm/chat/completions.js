// POST /api/llm/chat/completions: Ask Atlas's model step, forwarded to OpenRouter with the key (see lib/llm-proxy.js).
import { complete } from '../../../lib/llm-proxy.js';

export function POST(request) {
  return complete(request);
}
