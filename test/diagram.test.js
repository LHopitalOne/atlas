import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitControl, parseFlow, toMermaid } from '../src/ask/diagram.js';
import { renderAnswer } from '../src/ask/format.js';

test('control lines split off in either order', () => {
  const a = splitControl('Body.\n\nFLOW: n1 > n2\nFOLLOWUPS: x | y');
  const b = splitControl('Body.\n\nFOLLOWUPS: x | y\nFLOW: n1 > n2');
  for (const r of [a, b]) {
    assert.equal(r.body.trim(), 'Body.');
    assert.equal(r.flow, 'n1 > n2');
    assert.deepEqual(r.followups, ['x', 'y']);
  }
});

test('control lines are taken out wherever the model puts them, however it dresses them', () => {
  const mid = splitControl('First.\nFLOW: n4 > n3 > n2\n\nThen more prose.\nFOLLOWUPS: a | b');
  assert.equal(mid.body, 'First.\n\nThen more prose.');
  assert.equal(mid.flow, 'n4 > n3 > n2');
  assert.deepEqual(mid.followups, ['a', 'b']);
  for (const line of ['**FLOW:** n1 > n2', '**FLOW**: n1 > n2', '`FLOW: n1 > n2`', '- FLOW: n1 > n2']) {
    const r = splitControl(`Body.\n\n${line}`);
    assert.equal(r.body, 'Body.', line);
    assert.equal(r.flow, 'n1 > n2', line);
  }
  const fenced = splitControl('Body.\n\n```\nFLOW: n1 > n2\n```\n');
  assert.equal(fenced.body, 'Body.');
  assert.equal(fenced.flow, 'n1 > n2');
  assert.equal(splitControl('The flow: data goes in, then out.').body, 'The flow: data goes in, then out.');
});

test('step lines: routes with directions, stages with titles, unknown refs dropped', () => {
  assert.deepEqual(parseFlow('n1 > n2 < n3'), {
    stops: [
      { title: '', refs: ['n1'] },
      { title: '', refs: ['n2'] },
      { title: '', refs: ['n3'] },
    ],
    links: ['>', '<'],
  });
  const st = parseFlow('Data=n1,n2 | Draw=n3,[[n9]]', r => r !== 'n9');
  assert.deepEqual(st.stops, [
    { title: 'Data', refs: ['n1', 'n2'] },
    { title: 'Draw', refs: ['n3'] },
  ]);
  assert.equal(parseFlow('n1'), null, 'one stop is not a line');
});

test('Mermaid: routes keep the call direction, stages become subgraphs, labels are quoted', () => {
  const name = r => ({ n1: 'a', n2: 'b "quoted"', n3: 'c' })[r];
  const route = toMermaid({ flow: parseFlow('n1 > n2 < n3') }, name);
  assert.match(route, /^flowchart LR/);
  assert.match(route, /n1 -->\|calls\| n2/);
  assert.match(route, /n3 -->\|calls\| n2/, 'against the call: the later step calls the earlier one');
  assert.match(route, /#quot;quoted#quot;/);
  const stages = toMermaid({ flow: parseFlow('One=n1 | Two=n2,n3'), title: 'Q?' }, name);
  assert.match(stages, /^%% Q\?\nflowchart TD/);
  assert.match(stages, /subgraph s1\["Two"\]/);
  assert.match(stages, /s0 --> s1/);
  assert.match(
    toMermaid({ hops: [{ a: 1, b: 2, fwd: false }] }, r => r),
    /n2 -->\|calls\| n1/,
  );
});

test('the formatter returns the step line once an answer is complete, never while streaming', () => {
  const text = 'From a [[n1]] to b [[n2]].\n\nFLOW: n1 > n2\nFOLLOWUPS: q';
  assert.equal(
    renderAnswer(
      text,
      () => true,
      r => r,
    ).flow.stops.length,
    2,
  );
  assert.equal(
    renderAnswer(
      text,
      () => true,
      r => r,
      true,
    ).flow,
    null,
  );
  assert.ok(
    !renderAnswer(
      'x\n\nFLO',
      () => true,
      r => r,
      true,
    ).html.includes('FLO'),
    'a half-written control line stays hidden',
  );
});

test('citations are grouped by paragraph and list item, so separate findings get separate trails', () => {
  const r = renderAnswer(
    'Two loops:\n- a [[n1]] → b [[n2]] → a [[n1]]\n- c [[n3]] → d [[n4]] → c [[n3]]\n\nFLOW: n1 > n2 > n1',
    () => true,
    x => x,
  );
  assert.deepEqual(r.groups.slice(0, 2), [
    ['n1', 'n2', 'n1'],
    ['n3', 'n4', 'n3'],
  ]);
  const staged = renderAnswer(
    'x [[n1]]\n\nFLOW: A=n1,n2 | B=n3',
    () => true,
    x => x,
  );
  assert.deepEqual(staged.groups.at(-1), ['n2', 'n3'], 'stages join last-to-first');
});

test('SUMMARY lines ask for a summary picture, alongside FLOW and FOLLOWUPS', () => {
  const r = splitControl('Body.\n\nSUMMARY: impact n12\nFOLLOWUPS: a | b');
  assert.deepEqual(r.summary, { kind: 'impact', ref: 'n12' });
  assert.equal(splitControl('x\nFLOW: n1 > n2\nSUMMARY: tangle').summary.kind, 'tangle');
  assert.equal(
    renderAnswer(
      'x [[n1]]\n\nSUMMARY: impact n1',
      () => true,
      r2 => r2,
      true,
    ).summary,
    null,
    'not while streaming',
  );
});
