// The demo's Ask helper on Vercel (tools/demo/vercel): the host check, the key kept server-side, the model pinned.
import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { GET } from '../tools/demo/vercel/api/llm/ping.js';
import { POST } from '../tools/demo/vercel/api/llm/chat/completions.js';
import { MODEL, MAX_BODY, UPSTREAM } from '../tools/demo/vercel/lib/llm-proxy.js';
import { ASK_MODEL } from '../src/config.js';

const KEY = 'sk-or-test-not-a-real-key';
const HOST = 'atlas-demo.vercel.app';
const realFetch = globalThis.fetch;
let sent; // what the handler sent upstream

function request(path, { origin = `https://${HOST}`, referer, body, method = 'POST', headers = {} } = {}) {
  const h = { host: HOST, ...headers };
  if (origin) h.origin = origin;
  if (referer) h.referer = referer;
  return new Request(`https://${HOST}${path}`, { method, headers: h, body });
}
const chat = (opts = {}) =>
  request('/api/llm/chat/completions', {
    body: JSON.stringify({ model: 'someone/else', messages: [{ role: 'user', content: 'hi' }], max_tokens: 2500 }),
    headers: { 'content-type': 'application/json' },
    ...opts,
  });
const ping = (opts = {}) => request('/api/llm/ping', { method: 'GET', ...opts });

function upstream(status, payload) {
  globalThis.fetch = async (url, init) => {
    sent = { url, init, body: JSON.parse(init.body) };
    return new Response(JSON.stringify(payload), { status, headers: { 'content-type': 'application/json' } });
  };
}

beforeEach(() => {
  process.env.OPENROUTER_API_KEY = KEY;
  delete process.env.ALLOWED_HOSTS;
  sent = undefined;
  upstream(200, { choices: [{ message: { content: 'hello' } }] });
});
afterEach(() => {
  globalThis.fetch = realFetch;
  delete process.env.OPENROUTER_API_KEY;
});

async function read(r) {
  const text = await r.text();
  assert.ok(!text.includes(KEY), 'the key must never reach the page');
  return { status: r.status, data: text ? JSON.parse(text) : null };
}

test('the pinned model is the one the page asks for', () => {
  assert.equal(MODEL, ASK_MODEL);
});

test('ping says a key is here to the page on the same host (Referer, as a same-origin GET sends)', async () => {
  const r = await read(await GET(ping({ origin: null, referer: `https://${HOST}/` })));
  assert.deepEqual(r, { status: 200, data: { ok: true } });
});

test('a same-origin chat request goes to OpenRouter with the key added and the model overwritten', async () => {
  const r = await read(await POST(chat()));
  assert.equal(r.status, 200);
  assert.equal(r.data.choices[0].message.content, 'hello');
  assert.equal(sent.url, UPSTREAM);
  assert.equal(sent.init.headers.Authorization, `Bearer ${KEY}`);
  assert.equal(sent.init.headers['X-Title'], 'Atlas');
  assert.equal(sent.body.model, MODEL);
  assert.equal(sent.body.max_tokens, 2500, 'no cap: max_tokens passes through unchanged');
});

test('the forwarded host (behind Vercel) counts as the page host', async () => {
  const r = await read(
    await POST(
      chat({ origin: 'https://preview-123.vercel.app', headers: { 'x-forwarded-host': 'preview-123.vercel.app' } }),
    ),
  );
  assert.equal(r.status, 200);
});

test('another website, a sandboxed page or a request with no Origin or Referer gets 403', async () => {
  for (const origin of ['https://evil.example', 'null', '']) {
    sent = undefined;
    assert.equal((await read(await POST(chat({ origin })))).status, 403, origin);
    assert.equal((await read(await GET(ping({ origin })))).status, 403, origin);
    assert.equal(sent, undefined, 'nothing went upstream');
  }
});

test('ALLOWED_HOSTS lets other page hosts call', async () => {
  process.env.ALLOWED_HOSTS = 'demo.example.com, other.example';
  assert.equal((await read(await POST(chat({ origin: 'https://demo.example.com' })))).status, 200);
  assert.equal((await read(await POST(chat({ origin: 'https://third.example' })))).status, 403);
});

test('without a key, ping and chat answer 404', async () => {
  delete process.env.OPENROUTER_API_KEY;
  assert.deepEqual(await read(await GET(ping())), { status: 404, data: { ok: false } });
  assert.equal((await read(await POST(chat()))).status, 404);
  assert.equal(sent, undefined);
});

test('an oversized body is refused with 413, by its Content-Length or its real size', async () => {
  const big = JSON.stringify({ messages: [{ role: 'user', content: 'x'.repeat(MAX_BODY) }] });
  assert.equal((await read(await POST(chat({ body: big })))).status, 413);
  const lying = chat({ body: big, headers: { 'content-length': '10' } });
  assert.equal((await read(await POST(lying))).status, 413);
  assert.equal(sent, undefined);
});

test('a body that is not a JSON object is refused with 400', async () => {
  for (const body of ['not json', '[1,2]', 'null', '']) {
    assert.equal((await read(await POST(chat({ body })))).status, 400, body);
  }
  assert.equal(sent, undefined);
});

test("OpenRouter's error status and body pass through", async () => {
  upstream(429, { error: { message: 'rate limited' } });
  assert.deepEqual(await read(await POST(chat())), { status: 429, data: { error: { message: 'rate limited' } } });
  upstream(401, { error: { message: 'no auth' } });
  assert.equal((await read(await POST(chat()))).status, 401);
});

test('a network failure gives 502 with a short error', async () => {
  globalThis.fetch = async () => {
    throw new TypeError(`fetch failed for Bearer ${KEY}`);
  };
  assert.deepEqual(await read(await POST(chat())), { status: 502, data: { error: 'OpenRouter did not answer' } });
});
