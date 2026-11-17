/**
 * Ask Atlas on Vercel: the two routes `atlas serve` answers (bridge/atlas_bridge/cli/serve.py, LlmProxy), as Vercel
 * functions, so OPENROUTER_API_KEY stays on the server and never reaches the page. api/llm/ping.js and
 * api/llm/chat/completions.js call these. Web Request/Response handlers and the global fetch: no dependencies.
 *
 * Only the demo's own page may call: the request's Origin (or Referer) host must be the host it was sent to, or one
 * listed in ALLOWED_HOSTS. That stops other websites spending the key from their visitors' browsers; a script outside
 * a browser can send any Origin it likes, so it does not stop a determined caller.
 */
export const UPSTREAM = 'https://openrouter.ai/api/v1/chat/completions';
export const MODEL = 'meta/muse-ember'; // the one model the key is for; must match ASK_MODEL in src/config.js
export const MAX_BODY = 4_000_000; // bytes, as serve.py: a conversation with tool results; Vercel's own cap is 4.5 MB
const TIMEOUT_MS = 290_000; // under maxDuration in vercel.json (300 s), so a stuck model gets our 502, not Vercel's 504
const KEY_VARIABLE = 'OPENROUTER_API_KEY';
const HOSTS_VARIABLE = 'ALLOWED_HOSTS'; // more page hosts, comma-separated; same origin only (no CORS headers here)

function json(status, data) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

function hostOf(url) {
  try {
    return new URL(url).host.toLowerCase();
  } catch (_) {
    return ''; // absent, or "null" from a sandboxed page
  }
}

/** Whether a browser showing the demo's own page sent this request. */
export function fromOwnPage(request) {
  const h = request.headers;
  const own = (h.get('x-forwarded-host') || h.get('host') || '').split(',')[0].trim().toLowerCase();
  const from = hostOf(h.get('origin') || h.get('referer') || '');
  const more = (process.env[HOSTS_VARIABLE] || '')
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter(Boolean);
  return from !== '' && (from === own || more.includes(from));
}

/** GET /api/llm/ping: 200 {ok: true} when this server holds a key, 404 {ok: false} when it does not. */
export function ping(request) {
  if (!fromOwnPage(request)) return json(403, { ok: false, error: 'not from this page' });
  const ok = Boolean(process.env[KEY_VARIABLE]);
  return json(ok ? 200 : 404, { ok });
}

// The chat request as an object, or { status, error } when it is too large or not JSON.
async function readBody(request) {
  if (Number(request.headers.get('content-length') || 0) > MAX_BODY) return { status: 413, error: 'request too large' };
  const bytes = await request.arrayBuffer();
  if (bytes.byteLength > MAX_BODY) return { status: 413, error: 'request too large' };
  try {
    const data = JSON.parse(new TextDecoder().decode(bytes));
    if (data && typeof data === 'object' && !Array.isArray(data)) return { data };
  } catch (_) {
    // falls through to the refusal
  }
  return { status: 400, error: 'not JSON' };
}

/** POST /api/llm/chat/completions: forwards an OpenAI-style chat request to OpenRouter with the key added, always for
 * MODEL, and passes back OpenRouter's status and body. */
export async function complete(request) {
  if (!fromOwnPage(request)) return json(403, { error: 'not from this page' });
  const key = process.env[KEY_VARIABLE] || '';
  if (!key) return json(404, { error: 'not here' });
  const body = await readBody(request);
  if (!body.data) return json(body.status, { error: body.error });
  try {
    const r = await fetch(UPSTREAM, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json', 'X-Title': 'Atlas' },
      body: JSON.stringify({ ...body.data, model: MODEL }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    const payload = await r.arrayBuffer();
    return new Response(payload, {
      status: r.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    });
  } catch (_) {
    return json(502, { error: 'OpenRouter did not answer' });
  }
}
