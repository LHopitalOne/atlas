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

test('diagram layout: stage boxes stack without overlapping, pills stay inside their box and the width', async () => {
  const { layoutFlow, parseFlow } = await import('../src/ask/diagram.js');
  const flow = parseFlow('Data=n1,n2,n3 | Upload=n4 | Draw=n5,n6,n7,n8,n9');
  const L = layoutFlow(flow, { width: 300, textWidth: s => s.length * 7.2, nameOf: r => 'function_' + r });
  assert.equal(L.boxes.length, 3);
  assert.equal(L.arrows.length, 2);
  for (let k = 1; k < L.boxes.length; k++) assert.ok(L.boxes[k].y >= L.boxes[k - 1].y + L.boxes[k - 1].h + 20);
  for (const n of L.nodes) {
    const b = L.boxes[n.stage];
    assert.ok(n.x >= b.x && n.x + n.w <= b.x + b.w && n.y >= b.y && n.y + n.h <= b.y + b.h, `${n.ref} inside its box`);
    assert.ok(n.x + n.w <= 300);
  }
  assert.equal(L.height, L.boxes[2].y + L.boxes[2].h);
});

test('diagram layout: a route is a centred chain with one arrow per link', async () => {
  const { layoutFlow, parseFlow } = await import('../src/ask/diagram.js');
  const L = layoutFlow(parseFlow('n1 > n2 < n3'), { width: 300, textWidth: s => s.length * 7, nameOf: r => r });
  assert.equal(L.boxes.length, 0);
  assert.deepEqual(
    L.arrows.map(a => a.kind),
    ['>', '<'],
  );
  for (const n of L.nodes) assert.ok(Math.abs(n.x + n.w / 2 - 150) < 1);
});
