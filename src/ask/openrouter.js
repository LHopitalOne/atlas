/**
 * Asking a model on OpenRouter from the page (ASK_MODEL, Meta's Muse Ember by default), with the same tools and
 * rules as the Claude engine. Two ways to reach it, so no key is ever written into the page:
 * - `atlas serve` serves the page with a local proxy that adds OPENROUTER_API_KEY on the way out;
 * - anywhere else, the viewer gives their own key once; it stays in this tab's sessionStorage and goes only to
 *   openrouter.ai.
 * The model calls the map's tools in a loop (OpenAI-style tool calls) until it answers, at most ASK_LLM.maxSteps.
 */
import { ASK_LLM, ASK_MODEL } from '../config.js';
import { RULES, STEP } from './claude.js';

let transport; // { url, headers, via: 'proxy'|'key' } once known, null when there is none yet

function storedKey() {
  try {
    return sessionStorage.getItem(ASK_LLM.keyStore) || '';
  } catch (_) {
    return '';
  }
}

/** How this page reaches OpenRouter: the local proxy when `atlas serve` is serving it, else a stored key; or null. */
export async function llmTransport() {
  if (transport) return transport;
  try {
    const r = await fetch(`${ASK_LLM.proxy}/ping`, { cache: 'no-store' });
    if (r.ok) return (transport = { url: `${ASK_LLM.proxy}/chat/completions`, headers: {}, via: 'proxy' });
  } catch (_) {
    // not served by `atlas serve`
  }
  const key = storedKey();
  if (key) return (transport = keyTransport(key));
  return null;
}

function keyTransport(key) {
  return {
    url: `${ASK_LLM.direct}/chat/completions`,
    headers: { Authorization: `Bearer ${key}`, 'X-Title': 'Atlas' },
    via: 'key',
  };
}

/** Use a key the viewer gave for the rest of this tab's life. */
export function useKey(key) {
  try {
    sessionStorage.setItem(ASK_LLM.keyStore, key);
  } catch (_) {
    // storage blocked: the key still works until the page closes
  }
  transport = keyTransport(key);
}

/** Forget the viewer's key (after OpenRouter refuses it). */
export function forgetKey() {
  try {
    sessionStorage.removeItem(ASK_LLM.keyStore);
  } catch (_) {
    // nothing stored
  }
  transport = null;
}

const asFunction = t => ({
  type: 'function',
  function: {
    name: t.name,
    description: t.description,
    parameters: t.inputSchema || { type: 'object', properties: {} },
  },
});

async function complete(messages, tools, signal) {
  const t = await llmTransport();
  if (!t) throw { code: 'no_key', message: 'Give an OpenRouter key to ask the model.' };
  const body = {
    model: ASK_MODEL,
    messages,
    max_tokens: ASK_LLM.maxTokens,
    reasoning: { effort: 'low' },
    ...(tools.length ? { tools: tools.map(asFunction) } : {}),
  };
  const r = await fetch(t.url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...t.headers },
    body: JSON.stringify(body),
    signal,
  });
  if (r.status === 401 || r.status === 403) {
    if (t.via === 'key') forgetKey();
    throw { code: 'no_key', message: 'OpenRouter refused the key.' };
  }
  if (r.status === 429) throw { code: 'rate_limited' };
  if (!r.ok) throw { code: 'failed', message: `OpenRouter answered ${r.status}` };
  const data = await r.json();
  return (data.choices && data.choices[0] && data.choices[0].message) || {};
}

function runTool(byName, call, onStep, steps, nameOf) {
  const fn = call.function || {};
  const tool = byName.get(fn.name);
  let args = {};
  try {
    args = fn.arguments ? JSON.parse(fn.arguments) : {};
  } catch (_) {
    return { error: 'arguments were not valid JSON' };
  }
  if (!tool) return { error: `no tool named ${fn.name}` };
  onStep((steps[tool.name] || (() => tool.name))(args, nameOf), tool.name);
  try {
    return tool.run(args);
  } catch (e) {
    return { error: String((e && e.message) || e) };
  }
}

/**
 * @param {{question:string, history:{role:string,content:string}[], context:string, tools:object[], nameOf:(ref:string)=>string,
 *   onText:(text:string)=>void, onStep:(label:string, tool:string)=>void, signal:AbortSignal}} a
 * @returns {Promise<string>} the full answer
 */
export async function askOpenRouter({ question, history, context, tools, nameOf, onText, onStep, signal }) {
  const byName = new Map(tools.map(t => [t.name, t]));
  const messages = [
    { role: 'system', content: `${RULES}\n\nWhat the user is looking at:\n${context}` },
    ...history,
    { role: 'user', content: question },
  ];
  for (let round = 0; round < ASK_LLM.maxSteps; round++) {
    const msg = await complete(messages, round < ASK_LLM.maxSteps - 1 ? tools : [], signal);
    const calls = msg.tool_calls || [];
    if (!calls.length) {
      const text = (msg.content || '').trim();
      onText(text);
      return text;
    }
    messages.push({ role: 'assistant', content: msg.content || '', tool_calls: calls });
    for (const call of calls) {
      const result = runTool(byName, call, onStep, STEP, nameOf);
      const content = JSON.stringify(result).slice(0, ASK_LLM.maxToolChars);
      messages.push({ role: 'tool', tool_call_id: call.id, content });
    }
  }
  throw { code: 'failed', message: 'The model kept looking things up without answering.' };
}
