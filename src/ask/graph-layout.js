/**
 * Small directed graphs for answers (about 12 nodes or fewer), laid out in layers the way Mermaid's engine does, but
 * drawn by Atlas so items link to the map. Pure.
 *
 *   1. breakCycles   edges that close a loop are marked `back`
 *   2. layer         callers above what they call; every edge gets a waypoint in each half-step it crosses
 *   3. order         barycentre sweeps to reduce crossings
 *   4. place         balanced: placed pushing left-first and right-first, then averaged, so parents sit centred
 *                    over children and the whole drawing is centred
 *   5. route         leave the bottom of a box vertically, arrive at the top vertically (arrowheads never tilt),
 *                    basis splines through the waypoints; loop-backs go up the right side and enter from below
 */

/** A smooth curve through points, like d3's curveBasis (Mermaid's default). */
export function basisPath(pts) {
  if (pts.length < 3) return pts.length === 2 ? `M${pts[0][0]} ${pts[0][1]}L${pts[1][0]} ${pts[1][1]}` : '';
  let d = `M${pts[0][0]} ${pts[0][1]}`,
    [x0, y0] = pts[0],
    [x1, y1] = pts[1];
  d += `L${(5 * x0 + x1) / 6} ${(5 * y0 + y1) / 6}`;
  const seg = (x, y) => {
    d += `C${(2 * x0 + x1) / 3} ${(2 * y0 + y1) / 3},${(x0 + 2 * x1) / 3} ${(y0 + 2 * y1) / 3},${(x0 + 4 * x1 + x) / 6} ${(y0 + 4 * y1 + y) / 6}`;
  };
  for (let k = 2; k < pts.length; k++) {
    seg(pts[k][0], pts[k][1]);
    [x0, y0, x1, y1] = [x1, y1, pts[k][0], pts[k][1]];
  }
  seg(x1, y1);
  return d + `L${x1} ${y1}`;
}

/** 1. Depth-first from the first node (the answer's starting point); an edge into a node still on the stack is a back edge. */
function breakCycles(n, at, edges) {
  const state = new Uint8Array(n),
    out = Array.from({ length: n }, () => []);
  edges.forEach(e => out[at.get(e.from)].push(e));
  for (let s = 0; s < n; s++) {
    if (state[s]) continue;
    const stack = [[s, 0]];
    state[s] = 1;
    while (stack.length) {
      const top = stack[stack.length - 1],
        u = top[0];
      if (top[1] < out[u].length) {
        const e = out[u][top[1]++],
          v = at.get(e.to);
        if (state[v] === 1) e.back = true;
        else if (!state[v]) {
          state[v] = 1;
          stack.push([v, 0]);
        }
      } else {
        state[u] = 2;
        stack.pop();
      }
    }
  }
}

/** 2. Layers by longest path (real nodes on even rows); a waypoint in every row an edge crosses. */
function layer(graph, at, fwd, textWidth) {
  const n = graph.nodes.length,
    lay = new Array(n).fill(0);
  for (let pass = 0; pass < n; pass++) {
    let changed = false;
    for (const e of fwd) {
      const a = at.get(e.from),
        b = at.get(e.to);
      if (lay[b] < lay[a] + 1) {
        lay[b] = lay[a] + 1;
        changed = true;
      }
    }
    if (!changed) break;
  }
  const V = graph.nodes.map((nd, k) => ({
    real: true,
    row: lay[k] * 2,
    w: Math.ceil(textWidth(nd.label)) + 20 + (nd.pad || 0),
  }));
  const links = [],
    chain = fwd.map(() => []);
  fwd.forEach((e, ei) => {
    let prev = at.get(e.from);
    const target = at.get(e.to);
    for (let r = V[prev].row + 1; r < V[target].row; r++) {
      V.push({ real: false, row: r, w: 2 });
      links.push([prev, V.length - 1]);
      chain[ei].push(V.length - 1);
      prev = V.length - 1;
    }
    links.push([prev, target]);
  });
  return { lay, V, links, chain };
}

/** 3. Barycentre ordering, alternating down and up sweeps. */
function order(V, links) {
  const R = Math.max(0, ...V.map(v => v.row)) + 1,
    rows = Array.from({ length: R }, () => []);
  V.forEach((v, k) => rows[v.row].push(k));
  const up = V.map(() => []),
    down = V.map(() => []);
  links.forEach(([a, b]) => {
    down[a].push(b);
    up[b].push(a);
  });
  const pos = new Float64Array(V.length);
  rows.forEach(r => r.forEach((k, i) => (pos[k] = i)));
  for (let sweep = 0; sweep < 8; sweep++) {
    const goingDown = sweep % 2 === 0,
      seq = goingDown ? [...rows.keys()].slice(1) : [...rows.keys()].reverse().slice(1);
    for (const li of seq) {
      const nb = goingDown ? up : down;
      const bary = k => (nb[k].length ? nb[k].reduce((acc, j) => acc + pos[j], 0) / nb[k].length : pos[k]);
      rows[li].sort((a, b) => bary(a) - bary(b));
      rows[li].forEach((k, i) => (pos[k] = i));
    }
  }
  return { rows, up, down };
}

/** 4. Balanced x: place pushing left-first and right-first, each pulled towards neighbours; average the two. */
function place(V, rows, up, down, gap) {
  const sep = (a, b) => (V[a].w + V[b].w) / 2 + (V[a].real && V[b].real ? gap : V[a].real || V[b].real ? 10 : 7);
  const run = leftFirst => {
    const cx = new Float64Array(V.length);
    rows.forEach(r => r.forEach((k, i) => (cx[k] = i ? cx[r[i - 1]] + sep(r[i - 1], k) : 0)));
    const settle = (r, want) => {
      r.forEach(k => (cx[k] = want(k)));
      const fwdPass = () => {
        for (let i = 1; i < r.length; i++) cx[r[i]] = Math.max(cx[r[i]], cx[r[i - 1]] + sep(r[i - 1], r[i]));
      };
      const backPass = () => {
        for (let i = r.length - 2; i >= 0; i--) cx[r[i]] = Math.min(cx[r[i]], cx[r[i + 1]] - sep(r[i], r[i + 1]));
      };
      if (leftFirst) {
        fwdPass();
        backPass();
        fwdPass();
      } else {
        backPass();
        fwdPass();
        backPass();
      }
    };
    const mean = (ks, k) => (ks.length ? ks.reduce((acc, j) => acc + cx[j], 0) / ks.length : cx[k]);
    for (let it = 0; it < 14; it++) {
      for (let li = 1; li < rows.length; li++) settle(rows[li], k => mean(up[k], k));
      for (let li = rows.length - 2; li >= 0; li--) settle(rows[li], k => mean(down[k], k));
    }
    const mid = (Math.min(...V.map((v, k) => cx[k] - v.w / 2)) + Math.max(...V.map((v, k) => cx[k] + v.w / 2))) / 2;
    return cx.map(x => x - mid);
  };
  const a = run(true),
    b = run(false),
    cx = a.map((x, k) => (x + b[k]) / 2);
  // averaging can bring neighbours a little too close: restore spacing symmetrically
  for (const r of rows)
    for (let i = 1; i < r.length; i++) {
      const need = cx[r[i - 1]] + sep(r[i - 1], r[i]) - cx[r[i]];
      if (need > 0) for (let j = 0; j < r.length; j++) cx[r[j]] += j < i ? -need / 2 : need / 2;
    }
  return cx;
}

/**
 * @param {{nodes:{id:string, label:string, pad?:number}[], edges:{from:string, to:string}[]}} graph edges are calls
 * @param {{width:number, textWidth:(s:string)=>number, nodeH?:number, rankGap?:number, gap?:number}} o
 * @returns {{width:number, height:number, nodes:object[], edges:{from:string, to:string, back:boolean, d:string, points:number[][]}[], fits:boolean}}
 */
export function layoutGraph(graph, { width, textWidth, nodeH = 26, rankGap = 34, gap = 16 }) {
  const ids = graph.nodes.map(nd => nd.id),
    at = new Map(ids.map((id, k) => [id, k]));
  const edges = graph.edges
    .filter(e => at.has(e.from) && at.has(e.to) && e.from !== e.to)
    .map(e => ({ ...e, back: false }));
  breakCycles(ids.length, at, edges);
  const fwd = edges.filter(e => !e.back);
  const { lay, V, links, chain } = layer(graph, at, fwd, textWidth);
  const { rows, up, down } = order(V, links);
  const cx = place(V, rows, up, down, gap);
  const hasBack = edges.some(e => e.back),
    room = hasBack ? 28 : 0;
  const left = Math.min(...V.map((v, k) => cx[k] - v.w / 2)),
    right = Math.max(...V.map((v, k) => cx[k] + v.w / 2));
  const fits = right - left + room <= width,
    shift = (width - room) / 2 - (left + right) / 2;
  const half = (nodeH + rankGap) / 2,
    yOf = r => r * half,
    L = Math.max(0, ...lay) + 1;
  const X = k => cx[k] + shift;
  const nodes = graph.nodes.map((nd, k) => ({
    ...nd,
    x: X(k) - V[k].w / 2,
    y: yOf(V[k].row),
    w: V[k].w,
    h: nodeH,
    layer: lay[k],
  }));
  return {
    width,
    height: L * nodeH + (L - 1) * rankGap,
    nodes,
    edges: route(edges, fwd, nodes, at, chain, V, X, yOf, nodeH, width),
    fits,
  };
}

/** 5. Vertical exits and entries (so arrowheads point straight down), basis splines through the waypoints. */
function route(edges, fwd, nodes, at, chain, V, X, yOf, nodeH, width) {
  const lead = 9,
    clampX = (x, B) => Math.max(B.x + 9, Math.min(B.x + B.w - 9, x));
  return edges.map(e => {
    const A = nodes[at.get(e.from)],
      B = nodes[at.get(e.to)];
    const acx = A.x + A.w / 2,
      bcx = B.x + B.w / 2;
    if (e.back) {
      // up the right-hand side, then into the target from below with the arrowhead pointing straight up
      const side = Math.min(
        width - 3,
        Math.max(...nodes.filter(x => x.layer >= B.layer && x.layer <= A.layer).map(x => x.x + x.w)) + 20,
      );
      const ex = B.x + B.w - 14,
        sy = A.y + nodeH / 2,
        by = B.y + nodeH;
      const pts = [
        [A.x + A.w, sy],
        [side - 6, sy],
        [side, sy - 10],
        [side, by + 14],
        [ex + 8, by + 12],
        [ex, by + lead],
        [ex, by + 3],
      ];
      return { from: e.from, to: e.to, back: true, points: pts, d: basisPath(pts) };
    }
    const ei = fwd.findIndex(f => f.from === e.from && f.to === e.to);
    const via = chain[ei].map(k => [X(k), yOf(V[k].row) + nodeH / 2]);
    const next = via[0] || [bcx],
      prev = via[via.length - 1] || [acx];
    const sx = clampX(acx + (next[0] - acx) * 0.3, A),
      ex = clampX(bcx + (prev[0] - bcx) * 0.3, B);
    const sy = A.y + nodeH,
      ey = B.y - 3;
    const pts = [[sx, sy], [sx, sy + lead], ...via, [ex, ey - lead], [ex, ey]];
    return { from: e.from, to: e.to, back: false, points: pts, d: basisPath(pts) };
  });
}
