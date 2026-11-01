/**
 * Offline answerer: recognises the common questions (what does X do, what breaks if X changes, how does A reach B,
 * who uses X, what is this codebase) and answers them from the index with the same tools Claude uses, without AI.
 * Used when Claude is not available, and by the tests. Pure: returns text in the same format Claude is asked for.
 */
import { describe, impact, overview, resolve, route, search } from './tools.js';

const strip = s =>
  s
    .trim()
    .replace(/^the\s+/i, '')
    .replace(/[?.!]+$/, '')
    .replace(/^@/, '')
    .replace(/[`'"]/g, '')
    .trim();

/** Turn a phrase into a reference: exact name, @mention, "this"/"it" (the selection), or the best search match. */
function find(g, phrase, context) {
  const p = strip(phrase || '');
  if (!p || /^(this|it|that|the selected one|the selection)$/i.test(p)) return context || null;
  const exact = resolve(g, p);
  if (exact) return exact.t + exact.id;
  const hit = search(g, { query: p, limit: 1 })[0];
  return hit ? hit.ref : null;
}

const cite = x => `${x.name} [[${x.ref}]]`;
const list = (xs, n = 5) => xs.slice(0, n).map(cite).join(', ') + (xs.length > n ? `, and ${xs.length - n} more` : '');

const INTENTS = [
  {
    key: 'overview',
    re: /^(give me an? )?(overview|summary)|what('s| is) (this|the) (codebase|code|system|map|repo)|how is (this|the|it).*(organi[sz]ed|structured)/i,
  },
  {
    key: 'route',
    re: /^(how|does|can)\s+(does\s+|do\s+)?(.+?)\s+(reach|call|get to|talk to|connect to|depend on|use|lead to)\s+(.+)$/i,
    a: 3,
    b: 5,
  },
  { key: 'route', re: /^(route|path|way)\s+from\s+(.+?)\s+to\s+(.+)$/i, a: 2, b: 3 },
  { key: 'impact', re: /(break|affect|impact).*?(if i change|when i change|changing|change to|change)\s+(.+)$/i, a: 3 },
  { key: 'impact', re: /^(what('s| is) the )?impact of\s+(.+)$/i, a: 3 },
  { key: 'usedBy', re: /^(who|what)\s+(uses|calls|depends on|needs)\s+(.+)$/i, a: 3 },
  { key: 'describe', re: /^(what|where)\s+(does|is)\s+(.+?)(\s+do|\s+for)?$/i, a: 3 },
  { key: 'describe', re: /^(explain|describe|tell me about|show me)\s+(.+)$/i, a: 2 },
];

/** Which question is this, and about what? */
export function parseQuestion(q) {
  const text = q.trim().replace(/[?!.]+$/, '');
  for (const it of INTENTS) {
    const m = text.match(it.re);
    if (m) return { key: it.key, a: it.a ? m[it.a] : null, b: it.b ? m[it.b] : null };
  }
  return { key: 'search', a: text };
}

function answerOverview(g, step) {
  step('Read the map overview');
  const o = overview(g),
    t = o.totals,
    top = o.repositories[0];
  const repos = o.repositories
    .slice(0, 5)
    .map(r => `- ${r.name} [[${r.ref}]]: ${r.services} services in ${r.domains} domains`)
    .join('\n');
  return `This map has ${t.repositories} repositories, ${t.domains} domains, ${t.services} services and ${t.endpoints} endpoints, joined by ${t.contracts} contracts.\n\nThe largest repositories:\n${repos}\n\nFOLLOWUPS: What are the hubs? | ${top ? `Tell me about ${top.name}` : 'What breaks most often?'}`;
}

function answerRoute(g, intent, need, step) {
  const a = need(intent.a),
    b = need(intent.b);
  step('Found a route');
  const r = route(g, { from: a, to: b });
  if (!r.found)
    return `${r.from} and ${r.to} aren't connected on the map, in either direction.\n\nFOLLOWUPS: What does ${r.from} depend on? | Who uses ${r.to}?`;
  const steps = r.steps
    .map((s, k) =>
      k === 0 ? `- Start at ${cite(s)}` : `- ${s.step === 'calls' ? 'calls' : 'is called by'} ${cite(s)}`,
    )
    .join('\n');
  const how = r.followsCalls
    ? ', following calls'
    : '. No chain of calls exists, so part of this route goes against the call direction';
  return `${r.hops} hop${r.hops === 1 ? '' : 's'}${how}:\n${steps}\n\nFOLLOWUPS: Show this as directions | What breaks if I change ${r.steps[r.steps.length - 1].name}?`;
}

function answerImpact(g, intent, need, step) {
  const im = impact(g, { ref: need(intent.a) });
  step(`Checked the impact of ${im.name}`);
  const more = `\n\nFOLLOWUPS: What does ${im.name} do? | ${im.affects ? `Show me the code of ${im.name}` : `What does ${im.name} depend on?`}`;
  if (!im.affects) return `Nothing calls ${im.name} [[${im.ref}]], so a change there stays there.${more}`;
  const s = n => (n === 1 ? '' : 's');
  return `Changing ${im.name} [[${im.ref}]] can affect ${im.affects} service${s(im.affects)} in ${im.repositories} repositor${im.repositories === 1 ? 'y' : 'ies'}. ${im.directCallers} call${im.directCallers === 1 ? 's' : ''} it directly; the rest reach it through them.\n\nNearest first: ${list(im.nearest, 6)}.${more}`;
}

function answerTerritory(d) {
  const inner =
    d.kind === 'repository'
      ? `${d.domainCount} domains, including ${list(d.domains, 6)}`
      : `${d.services} services, including ${list(d.examples, 6)}`;
  return `${d.name} [[${d.ref}]] is a ${d.kind}${d.repository ? ` in ${d.repository}` : ''} with ${inner}.\n\nFOLLOWUPS: What are its hubs? | What depends on ${d.name}?`;
}

function answerUsedBy(d) {
  const users = d.usedBy || d.calledBy || [];
  const body = users.length
    ? `${d.name} [[${d.ref}]] is used by ${list(users, 8)}.`
    : `Nothing on the map uses ${d.name} [[${d.ref}]].`;
  return `${body}\n\nFOLLOWUPS: What breaks if I change ${d.name}? | What does ${d.name} do?`;
}

function answerDescribe(g, d, intent) {
  const lines = [
    `${d.name} [[${d.ref}]] is ${d.kind === 'service' ? 'a definition' : 'an endpoint'} in ${d.where}. ${d.summary || 'It has no description in the code yet.'}`,
  ];
  const facts = [
    d.roles && d.roles.length && `- Role: ${d.roles.join('; ')}`,
    d.usedBy && `- Used by ${d.usedByCount}${d.usedBy.length ? `: ${list(d.usedBy, 4)}` : ''}`,
    d.dependsOn && `- Depends on ${d.dependsOnCount}${d.dependsOn.length ? `: ${list(d.dependsOn, 4)}` : ''}`,
    d.calledBy && `- Called by ${d.calledBy.length ? list(d.calledBy, 4) : 'nothing on the map'}`,
    d.location && `- Source: \`${d.location}\``,
  ].filter(Boolean);
  if (facts.length) lines.push(facts.join('\n'));
  if (intent.key === 'search' && strip(intent.a).split(/\s+/).length > 2) {
    const more = search(g, { query: intent.a, limit: 5 }).filter(x => x.ref !== d.ref);
    if (more.length) lines.push(`Also related: ${list(more, 4)}.`);
  }
  return `${lines.join('\n\n')}\n\nFOLLOWUPS: What breaks if I change ${d.name}? | Who uses ${d.name}?`;
}

/**
 * Answer a question from the index.
 * @param {object} g graph
 * @param {string} q question
 * @param {{context?: string|null, onStep?: (label:string)=>void}} [opts] context = ref of the selected item
 * @returns {string} answer text with [[ref]] citations and a FOLLOWUPS line
 */
export function answerLocally(g, q, { context = null, onStep = () => {} } = {}) {
  const intent = parseQuestion(q);
  const need = phrase => {
    const ref = find(g, phrase, context);
    onStep(`Searched the index for “${strip(phrase || 'the selection')}”`);
    if (!ref)
      throw new Error(`I couldn't find “${strip(phrase || '')}” on the map. Try its exact name, or select it first.`);
    return ref;
  };
  try {
    if (intent.key === 'overview') return answerOverview(g, onStep);
    if (intent.key === 'route') return answerRoute(g, intent, need, onStep);
    if (intent.key === 'impact') return answerImpact(g, intent, need, onStep);
    const d = describe(g, { ref: need(intent.a) });
    onStep(`Described ${d.name}`);
    if (d.kind === 'repository' || d.kind === 'domain') return answerTerritory(d);
    if (intent.key === 'usedBy') return answerUsedBy(d);
    return answerDescribe(g, d, intent);
  } catch (e) {
    return `${e.message}\n\nFOLLOWUPS: What is this codebase? | What are the hubs?`;
  }
}
