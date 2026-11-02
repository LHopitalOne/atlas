import { test } from 'node:test';
import assert from 'node:assert/strict';
import { layoutGraph } from '../src/ask/graph-layout.js';

const tw = s => s.length * 7.2;
const g = (names, calls) => ({
  nodes: names.map(n => ({ id: n, label: n })),
  edges: calls.map(([a, b]) => ({ from: a, to: b })),
});
const byId = L => Object.fromEntries(L.nodes.map(n => [n.id, n]));

test('callers sit above what they call; a shared callee forms a V', () => {
  const L = layoutGraph(
    g(
      ['runSearch', 'drawResults', 'theme', 'render', 'drawEdges'],
      [
        ['runSearch', 'drawResults'],
        ['drawResults', 'theme'],
        ['render', 'theme'],
        ['render', 'drawEdges'],
      ],
    ),
    { width: 350, textWidth: tw },
  );
  const n = byId(L);
  assert.ok(n.runSearch.layer < n.drawResults.layer && n.drawResults.layer < n.theme.layer);
  assert.ok(n.render.layer < n.theme.layer && n.render.layer < n.drawEdges.layer);
  assert.ok(L.fits);
  assert.ok(
    L.edges.every(e => !e.back),
    'no loops, no back edges',
  );
});

test('a loop gets exactly one back edge, curving up the side', () => {
  const names = ['a', 'b', 'c', 'd'];
  const L = layoutGraph(
    g(names, [
      ['a', 'b'],
      ['b', 'c'],
      ['c', 'd'],
      ['d', 'a'],
    ]),
    { width: 300, textWidth: tw },
  );
  assert.equal(L.edges.filter(e => e.back).length, 1);
  assert.deepEqual(
    L.nodes.map(x => x.layer),
    [0, 1, 2, 3],
    'the loop unrolls top to bottom from its start',
  );
});

test('nodes in a layer never overlap, and wide layers report that they do not fit', () => {
  const L = layoutGraph(
    g(
      ['root', 'x1', 'x2', 'x3'],
      [
        ['root', 'x1'],
        ['root', 'x2'],
        ['root', 'x3'],
      ],
    ),
    { width: 300, textWidth: tw },
  );
  const row = L.nodes.filter(x => x.layer === 1).sort((a, b) => a.x - b.x);
  for (let k = 1; k < row.length; k++) assert.ok(row[k].x >= row[k - 1].x + row[k - 1].w);
  const wide = layoutGraph(
    g(
      ['r', ...Array.from({ length: 12 }, (_, k) => 'caller_' + k)],
      Array.from({ length: 12 }, (_, k) => ['caller_' + k, 'r']),
    ),
    { width: 350, textWidth: tw },
  );
  assert.equal(wide.fits, false, '12 callers side by side do not fit: the answer should summarise instead');
});

test('a long edge bends around the boxes it would cross, through waypoints', () => {
  // render -> theme skips a layer (theme sits below drawResults); its waypoint must not sit inside any box
  const L = layoutGraph(
    g(
      ['runSearch', 'drawResults', 'theme', 'render', 'drawEdges'],
      [
        ['runSearch', 'drawResults'],
        ['drawResults', 'theme'],
        ['render', 'theme'],
        ['render', 'drawEdges'],
      ],
    ),
    { width: 350, textWidth: tw },
  );
  const n = byId(L);
  if (n.theme.layer - n.render.layer > 1) {
    const e = L.edges.find(x => x.from === 'render' && x.to === 'theme');
    for (const [x, y] of e.points.slice(1, -1))
      for (const b of L.nodes)
        assert.ok(!(x > b.x && x < b.x + b.w && y > b.y && y < b.y + b.h), `waypoint (${x},${y}) is inside ${b.id}`);
  }
});

test('a straight chain stays straight', () => {
  const L = layoutGraph(
    g(
      ['a', 'b', 'c'],
      [
        ['a', 'b'],
        ['b', 'c'],
      ],
    ),
    { width: 300, textWidth: tw },
  );
  const c = L.nodes.map(x => x.x + x.w / 2);
  assert.ok(Math.abs(c[0] - c[1]) < 0.5 && Math.abs(c[1] - c[2]) < 0.5);
});

test('arrowheads never tilt: every arrow arrives vertically (down into a box, or up from below for a loop)', () => {
  const cases = [
    g(
      ['a', 'b', 'c', 'd'],
      [
        ['a', 'b'],
        ['b', 'c'],
        ['c', 'd'],
        ['d', 'a'],
      ],
    ),
    g(
      ['p', 'q', 'x', 'y', 'z'],
      [
        ['p', 'x'],
        ['q', 'x'],
        ['x', 'y'],
        ['x', 'z'],
        ['y', 'z'],
      ],
    ),
  ];
  for (const graph of cases) {
    const L = layoutGraph(graph, { width: 320, textWidth: tw });
    for (const e of L.edges) {
      const [p, q] = e.points.slice(-2);
      assert.ok(Math.abs(p[0] - q[0]) < 0.01, `${e.from}->${e.to} arrives vertically`);
      assert.ok(e.back ? q[1] < p[1] : q[1] > p[1], e.back ? 'loop-back points up' : 'points down');
    }
  }
});

test('a parent with two children sits centred over them', () => {
  const L = layoutGraph(
    g(
      ['root', 'left_child', 'right_child'],
      [
        ['root', 'left_child'],
        ['root', 'right_child'],
      ],
    ),
    { width: 320, textWidth: tw },
  );
  const n = byId(L),
    mid = (n.left_child.x + n.left_child.w / 2 + n.right_child.x + n.right_child.w / 2) / 2;
  assert.ok(Math.abs(n.root.x + n.root.w / 2 - mid) < 1);
  const lo = Math.min(...L.nodes.map(x => x.x)),
    hi = Math.max(...L.nodes.map(x => x.x + x.w));
  assert.ok(Math.abs((lo + hi) / 2 - 160) < 1, 'and the drawing as a whole is centred');
});

test('cycles: a racetrack where every arrowhead is axis-aligned and every step joins the next', async () => {
  const { layoutLoop } = await import('../src/ask/graph-layout.js');
  for (const names of [
    ['a', 'b'],
    ['a', 'b', 'c'],
    ['p', 'q', 'r', 's', 't', 'u', 'v'],
  ]) {
    const L = layoutLoop(
      names.map(x => ({ id: x, label: x })),
      { width: 330, textWidth: tw },
    );
    assert.equal(L.edges.length, names.length, 'one edge per step, the last closing the loop');
    assert.equal(L.edges.at(-1).to, names[0]);
    for (const e of L.edges) {
      const [p, q] = e.points.slice(-2);
      assert.ok(
        Math.abs(p[0] - q[0]) < 0.01 || Math.abs(p[1] - q[1]) < 0.01,
        `${e.from}->${e.to} arrowhead is axis-aligned`,
      );
    }
    assert.ok(L.fits);
  }
});
