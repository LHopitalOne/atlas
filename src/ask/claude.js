/**
 * Asking Claude from the page, through the viewer's own Claude account (the artifact `sample` capability).
 * Claude gets the same tools as the offline answerer and must cite every item it mentions as [[ref]].
 * Each call is memoryless, so the standing rules and the conversation so far are sent every time.
 */

const RULES = `You are Atlas, answering questions about a software codebase shown as a map: repositories contain domains, domains contain services (definitions), services expose endpoints, and services call each other.

Rules:
- Look things up with the tools. Never guess names, numbers or connections.
- Answer in plain, simple language. Be brief: at most about 120 words, optionally with a short list.
- Cite every map item you mention, right after its name, as [[ref]] using the ref from a tool result (n12, d3, r1). Never invent refs.
- If a summary is simulated or missing, say so rather than presenting it as fact.
- Use read_source only when the summary and signature are not enough, and say that you read the code.
- If something isn't on the map, say so.
- End with exactly one line: FOLLOWUPS: question 1 | question 2 | question 3 (short follow-up questions the user might ask next).`;

let sampleFn;
/** The sample function, or null when this view can't ask Claude (offline copy, other host, disabled). */
export async function claudeAvailable() {
  if (sampleFn !== undefined) return sampleFn;
  try {
    sampleFn =
      globalThis.claude && typeof globalThis.claude.use === 'function' ? await globalThis.claude.use('sample') : null;
  } catch (_) {
    sampleFn = null;
  }
  return sampleFn;
}
/** Stop using Claude for the rest of this view (after a decline or when sampling is disabled). */
export function disableClaude() {
  sampleFn = null;
}

const STEP = {
  search: i => `Searched the index for “${i.query}”`,
  describe: (i, name) => `Described ${name(i.ref)}`,
  impact: (i, name) => `Checked the impact of ${name(i.ref)}`,
  route: (i, name) => `Found a route from ${name(i.from)} to ${name(i.to)}`,
  overview: () => 'Read the map overview',
  read_source: (i, name) => `Read the code of ${name(i.ref)} (live, not stored)`,
};

/**
 * @param {{question:string, history:{role:string,content:string}[], context:string, tools:object[], nameOf:(ref:string)=>string,
 *   onText:(text:string)=>void, onStep:(label:string, tool:string)=>void, signal:AbortSignal}} a
 * @returns {Promise<string>} the full answer
 */
export async function askClaude({ question, history, context, tools, nameOf, onText, onStep, signal }) {
  const sample = await claudeAvailable();
  if (!sample) throw { code: 'unavailable', message: 'Claude is not available here.' };
  const input = [
    { role: 'user', content: `${RULES}\n\nWhat the user is looking at:\n${context}` },
    ...history,
    { role: 'user', content: question },
  ];
  const sampleTools = tools.map(t => ({
    name: t.name,
    description: t.description,
    ...(t.inputSchema ? { inputSchema: t.inputSchema } : {}),
    execute: args => {
      onStep((STEP[t.name] || (() => t.name))(args || {}, nameOf), t.name);
      return t.run(args || {});
    },
  }));
  const result = await sample(input, {
    tools: sampleTools,
    signal,
    cache: false,
    modelTier: 'quick',
    onText: ({ text }) => onText(text),
  });
  return result.text;
}
