import { test } from 'node:test';
import assert from 'node:assert/strict';
import './setup.js';
import { askOpenRouter } from '../src/ask/openrouter.js';

// A stand-in for `atlas serve`'s proxy and OpenRouter: the model first calls a tool, then answers with what it got.
function fakeServer(calls) {
  return async (url, opts = {}) => {
    if (url.endsWith('/ping')) return { ok: true, status: 200 };
    const body = JSON.parse(opts.body);
    calls.push(body);
    const toolResult = body.messages.find(m => m.role === 'tool');
    const message = toolResult
      ? { content: `Found ${JSON.parse(toolResult.content).count} items [[n1]].` }
      : { content: '', tool_calls: [{ id: 'c1', function: { name: 'search', arguments: '{"query":"mfa"}' } }] };
    return { ok: true, status: 200, json: async () => ({ choices: [{ message }] }) };
  };
}

test('the model looks things up with the map tools, then answers', async () => {
  const calls = [],
    steps = [];
  globalThis.fetch = fakeServer(calls);
  const tools = [{ name: 'search', description: 'find', inputSchema: { type: 'object' }, run: () => ({ count: 3 }) }];
  const text = await askOpenRouter({
    question: 'How does MFA work?',
    history: [],
    context: 'Nothing is selected.',
    tools,
    nameOf: r => r,
    onText: () => {},
    onStep: label => steps.push(label),
  });
  assert.equal(text, 'Found 3 items [[n1]].');
  assert.equal(calls.length, 2);
  assert.equal(calls[0].model, 'meta/muse-ember');
  assert.equal(calls[0].tools[0].function.name, 'search');
  assert.match(calls[0].messages[0].content, /You are Atlas/);
  assert.deepEqual(steps, ['Searched the index for “mfa”']);
});
