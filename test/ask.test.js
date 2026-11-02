import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import './setup.js';
import { buildSpec } from '../src/model/spec.js';
import { tinyGraph } from './helpers.js';
import { parseQuestion, answerLocally } from '../src/ask/local.js';
import { renderAnswer, splitFollowups } from '../src/ask/format.js';
import { resolve, search, route, impact, toolSet } from '../src/ask/tools.js';

const self = buildSpec(JSON.parse(readFileSync('generated/self-graph.json', 'utf8')));

test('questions are recognised', () => {
  assert.deepEqual(parseQuestion('What breaks if I change routeSearch?'), { key: 'impact', a: 'routeSearch', b: null });
  assert.equal(parseQuestion('How does placeLabels reach theme?').key, 'route');
  assert.equal(parseQuestion('what does routeSearch do').key, 'describe');
  assert.equal(parseQuestion('who uses store').key, 'usedBy');
  assert.equal(parseQuestion('what is this codebase?').key, 'overview');
  assert.equal(parseQuestion('label collision').key, 'search');
});

test('tools resolve names, refs and mentions', () => {
  const g = tinyGraph();
  assert.deepEqual(resolve(g, 's2'), { t: 'n', id: 2 });
  assert.deepEqual(resolve(g, '@s1'), { t: 'n', id: 1 });
  assert.deepEqual(resolve(g, 'n3'), { t: 'n', id: 3 });
  assert.deepEqual(resolve(g, 'A'), { t: 'r', id: 0 });
  assert.equal(resolve(g, 'n99'), null);
  assert.deepEqual(
    route(g, { from: 's0', to: 's2' }).steps.map(s => s.name),
    ['s0', 's1', 's2'],
  );
  assert.equal(impact(g, { ref: 's2' }).affects, 3);
});

test('search finds things by what they do', () => {
  const hits = search(self, { query: 'label collision' }).map(h => h.name);
  assert.ok(hits.includes('CollisionGrid') || hits.includes('placeLabels'), hits.join(', '));
});

test('local answers cite real items and suggest follow-ups', () => {
  const steps = [];
  const text = answerLocally(self, 'What breaks if I change routeSearch?', { onStep: s => steps.push(s) });
  const { html, refs, followups } = renderAnswer(
    text,
    ref => !!resolve(self, ref),
    ref => ref,
  );
  assert.match(text, /can affect \d+ service/);
  assert.ok(refs.length >= 2 && refs.every(r => resolve(self, r)));
  assert.ok(followups.length >= 1);
  assert.ok(steps.some(s => s.includes('impact')));
  assert.ok(!html.includes('[['));
});

test('"this" uses the selected item', () => {
  const ref = 'n' + resolve(self, 'routeSearch').id;
  assert.match(answerLocally(self, 'what does this do?', { context: ref }), /^routeSearch \[\[/);
});

test('formatter escapes text, drops citations to nothing, hides half-written ones while streaming', () => {
  const r = renderAnswer(
    '<b>x</b> uses `a<b` and **bold** [[n0]] [[n999]]\n\n- one [[n0]]\n- two',
    ref => ref === 'n0',
    () => 'name',
  );
  assert.ok(
    r.html.includes('&lt;b&gt;x&lt;/b&gt;') && r.html.includes('<code>a&lt;b</code>') && r.html.includes('<b>bold</b>'),
  );
  assert.deepEqual(r.refs, ['n0']);
  assert.equal((r.html.match(/class="cite"/g) || []).length, 2);
  assert.ok(r.html.includes('<ul><li>'));
  assert.equal(
    renderAnswer(
      'see [[n1',
      () => true,
      () => '',
      true,
    ).html,
    '<p>see</p>',
  );
  assert.deepEqual(splitFollowups('a\nFOLLOWUPS: x | y').followups, ['x', 'y']);
});

test('the tool set is described for Claude, with source reading only when available', () => {
  assert.deepEqual(
    toolSet(self).map(t => t.name),
    ['search', 'describe', 'impact', 'route', 'overview'],
  );
  assert.ok(toolSet(self, { readSource: () => null }).some(t => t.name === 'read_source'));
});

test('the rendering walkthrough cites real functions on the Self map', async () => {
  const { renderingScript, scriptFor, RENDER_QUESTION, DEMO_QUESTION } = await import('../src/ask/demo.js');
  assert.ok(RENDER_QUESTION.test(DEMO_QUESTION));
  const s = renderingScript(self);
  assert.equal(s.note, '', 'every name in the script exists in the Self index');
  const { refs } = renderAnswer(
    s.text,
    ref => !!resolve(self, ref),
    r => r,
  );
  assert.ok(refs.length >= 15, `cites ${refs.length} functions`);
  assert.ok(s.steps.every(st => !('ref' in st) || st.ref === undefined || st.ref === null || resolve(self, st.ref)));
  assert.equal(scriptFor(self, 'who uses store?').steps[0].label.startsWith('Searched'), true);
});

test('on a demo map the walkthrough says it is about Atlas itself', async () => {
  const { renderingScript } = await import('../src/ask/demo.js');
  const { build } = await import('../src/model/synthetic.js');
  assert.match(renderingScript(build(281)).note, /Switch to Self/);
});

test('the suggested questions for the Self map all have real answers', () => {
  const qs = ['What breaks if I change routeSearch?', 'Who uses store?', 'How does placeLabels reach requestRender?'];
  for (const q of qs) assert.doesNotMatch(answerLocally(self, q), /couldn't find|aren't connected/, q);
});

test('cycle questions are recognised and answered with a loop that closes on itself', () => {
  assert.equal(parseQuestion('Are there any dependency cycles?').key, 'cycles');
  assert.equal(parseQuestion('any circular imports between modules?').key, 'cycles');
  assert.deepEqual(parseQuestion('Is requestRender part of a cycle?'), { key: 'cycleOf', a: 'requestRender', b: null });
  assert.equal(parseQuestion('cycles involving frame').key, 'cycleOf');
  const text = answerLocally(self, 'Is requestRender part of a cycle?');
  const flow = text.match(/FLOW: (.*)/)[1].split(' > ');
  assert.equal(flow[0], flow.at(-1), 'the loop comes back to its start');
  assert.match(answerLocally(self, 'Is routeSearch in a cycle?'), /isn't part of any dependency cycle/);
  assert.match(answerLocally(self, 'Are there circular imports between modules?'), /Between modules: 1 cycle/);
});
