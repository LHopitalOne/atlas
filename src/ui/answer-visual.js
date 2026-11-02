/**
 * The picture under an answer, chosen by its shape:
 *   loop (FLOW starts and ends on the same item)  -> racetrack
 *   route or branching (one item per stop)        -> layered graph, centred (falls back to the stage list if too wide)
 *   stages (titled stops with several items)      -> stage list
 *   SUMMARY: impact <ref>                         -> counts and callers by module
 *   SUMMARY: tangle                               -> what holds the module tangle together
 * Every item is a button (data-ref): hover rings it on the map, click opens it. Boxes fade in, arrows draw themselves.
 */
import { store } from '../state.js';
import { layoutGraph, layoutLoop } from '../ask/graph-layout.js';
import { refName, resolve } from '../ask/tools.js';
import { impactOf } from '../graph/insights.js';
import { cyclesOf, shortestLoop } from '../graph/cycles.js';
import { tw } from '../render/canvas.js';
import { esc, fmt, MONO } from '../util/format.js';

const FONT = () => `400 12px ${MONO}`;
const STEP = 70; // ms between items appearing

/** Boxes and arrows as SVG; `start` gets a dot. */
function svgOf(L, start, at, i) {
  const out = [];
  L.edges.forEach((e, k) =>
    out.push(
      `<path class="ge${e.back ? ' back' : ''}" d="${e.d}" pathLength="1" data-at="${at + 80 + k * STEP}" marker-end="url(#ga${i})"/>`,
    ),
  );
  L.nodes.forEach((n, k) => {
    const first = n.id === start,
      name = refName(store.G, n.id);
    out.push(`<g class="gn${first ? ' start' : ''}" data-ref="${n.id}" data-at="${at + k * STEP}" tabindex="0" role="button" aria-label="${esc(name)}">
      <rect x="${n.x + 0.5}" y="${n.y + 0.5}" width="${n.w - 1}" height="${n.h - 1}" rx="7"/>${first ? `<circle cx="${n.x + 12}" cy="${n.y + n.h / 2}" r="2.5"/>` : ''}
      <text x="${n.x + n.w / 2 + (first ? 7 : 0)}" y="${n.y + n.h / 2 + 4}" text-anchor="middle">${esc(n.label)}</text></g>`);
  });
  return `<div class="gv"><svg viewBox="0 -3 ${L.width} ${L.height + 6}" width="${L.width}" height="${L.height + 6}" role="group" aria-label="Diagram of the answer">
    <defs><marker id="ga${i}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,1 L9,5 L0,9 z"/></marker></defs>${out.join('')}</svg></div>`;
}

const nodeOf = (ref, start) => ({ id: ref, label: refName(store.G, ref), pad: ref === start ? 14 : 0 });

/** A loop: the stops without repeating the start. */
function loopHTML(refs, width, at, i) {
  const L = layoutLoop(
    refs.map(r => nodeOf(r, refs[0])),
    { width, textWidth: s => tw(FONT(), s) },
  );
  return L.fits ? { html: svgOf(L, refs[0], at, i), items: refs.length } : null;
}

/** A route or branching answer: edges follow the call direction (> calls the next stop, < is called by it). */
function graphHTML(flow, width, at, i) {
  const refs = [...new Set(flow.stops.map(s => s.refs[0]))];
  const edges = flow.links.map((l, k) => {
    const a = flow.stops[k].refs[0],
      b = flow.stops[k + 1].refs[0];
    return l === '<' ? { from: b, to: a } : { from: a, to: b };
  });
  const L = layoutGraph({ nodes: refs.map(r => nodeOf(r, refs[0])), edges }, { width, textWidth: s => tw(FONT(), s) });
  return L.fits ? { html: svgOf(L, refs[0], at, i), items: refs.length } : null;
}

/** A pipeline: stage titles on a rail, items as text buttons. */
function stagesHTML(flow, at) {
  const rows = flow.stops.map((st, k) => {
    const items = st.refs
      .map(r => `<button class="si" data-ref="${r}">${esc(refName(store.G, r))}</button>`)
      .join('<span class="sep" aria-hidden="true"> · </span>');
    const end = k === 0 || k === flow.stops.length - 1;
    return `<li class="stg${end ? ' end' : ''}" data-at="${at + k * 45}"><span class="sd" aria-hidden="true"></span><div><div class="stt">${esc(st.title || `Step ${k + 1}`)}</div><div class="sit">${items}</div></div></li>`;
  });
  return { html: `<ol class="stages" aria-label="Steps">${rows.join('')}</ol>`, items: flow.stops.length * 0.65 };
}

/** Bars of counts by module (domain), biggest first. */
function bars(counts, at) {
  const top = counts.slice(0, 7),
    max = top[0] ? top[0][1] : 1;
  const rows = top.map(
    ([d, c], k) =>
      `<button class="bar" data-ref="d${d}" data-at="${at + 60 + k * 35}"><span class="bn">${esc(store.G.domName[d])}</span><span class="bt"><i style="width:${Math.max(4, (c / max) * 100).toFixed(0)}%"></i></span><span class="bc">${fmt(c)}</span></button>`,
  );
  const more =
    counts.length > top.length ? `<div class="sm-more">and ${counts.length - top.length} more modules</div>` : '';
  return rows.join('') + more;
}

/** "What breaks if I change X": counts, then everything affected grouped by module. */
function impactSummary(ref, at) {
  const g = store.G,
    e = resolve(g, ref);
  if (!e || e.t !== 'n') return null;
  const s = g.own(e.id),
    im = impactOf(g, s),
    by = new Map();
  for (const t of im.services) by.set(g.svcDom[t], (by.get(g.svcDom[t]) || 0) + 1);
  const counts = [...by].sort((a, b) => b[1] - a[1]);
  if (!counts.length) return null;
  return {
    html: `<div class="sum" data-at="${at}"><div class="sum-h"><b>${fmt(im.services.length)}</b> services could break · <b>${fmt(im.direct)}</b> call it directly · <b>${fmt(im.repos)}</b> ${im.repos === 1 ? 'repository' : 'repositories'}</div>
      <div class="sum-l">Affected, by module</div>${bars(counts, at)}</div>`,
    items: 4,
  };
}

/** The module tangle: which modules hold it together, and its tightest two-module loops. */
function tangleSummary(at) {
  const g = store.G,
    c = cyclesOf(g, 'domain'),
    grp = c.groups[0];
  if (!grp) return null;
  const inT = new Set(grp.members),
    deg = new Map(grp.members.map(d => [d, [0, 0]]));
  for (const a of grp.members)
    c.each(a, b => {
      if (inT.has(b)) {
        deg.get(a)[0]++;
        deg.get(b)[1]++;
      }
    });
  const hubs = [...deg].sort((x, y) => y[1][0] + y[1][1] - x[1][0] - x[1][1]).slice(0, 5);
  const pairs = [],
    seen = new Set();
  for (const m of grp.members) {
    const l = shortestLoop(m, grp.members, c.each);
    if (l && l.length === 3) {
      const key = [l[0], l[1]].sort().join();
      if (!seen.has(key)) {
        seen.add(key);
        pairs.push(l);
      }
    }
    if (pairs.length === 3) break;
  }
  const hubRows = hubs
    .map(
      ([d, [o, n]], k) =>
        `<button class="bar plain" data-ref="d${d}" data-at="${at + 60 + k * 35}"><span class="bn">${esc(g.domName[d])}</span><span class="bc2">imports ${o} · imported by ${n}</span></button>`,
    )
    .join('');
  const pairRows = pairs
    .map(
      ([a, b], k) =>
        `<div class="pair" data-at="${at + 260 + k * 35}"><button class="si" data-ref="d${a}">${esc(g.domName[a])}</button><span class="arr" aria-label="import each other">⇄</span><button class="si" data-ref="d${b}">${esc(g.domName[b])}</button></div>`,
    )
    .join('');
  return {
    html: `<div class="sum" data-at="${at}"><div class="sum-h"><b>${grp.members.length}</b> modules import each other in one loop</div>
      <div class="sum-l">Holding it together</div>${hubRows}${pairRows ? `<div class="sum-l" style="margin-top:12px">Tightest loops</div>${pairRows}` : ''}</div>`,
    items: 5,
  };
}

/**
 * The picture for a finished answer, or '' if it has none.
 * @param {{stops:object[], links:string[]}|null} flow
 * @param {{kind:string, ref?:string}|null} summary
 * @returns {{html:string, settle:number}} settle: when the picture has finished appearing (ms timestamp)
 */
export function visualHTML(flow, summary, at, i, width) {
  const parts = [];
  let t = at;
  if (flow) {
    const single = flow.stops.every(s => !s.title && s.refs.length === 1),
      refs = flow.stops.map(s => s.refs[0]);
    const isLoop = single && refs.length > 2 && refs[0] === refs[refs.length - 1];
    const pic = isLoop ? loopHTML(refs.slice(0, -1), width, t, i) : single ? graphHTML(flow, width, t, i) : null;
    const v = pic || stagesHTML(flow, t);
    parts.push(v.html);
    t += v.items * STEP + 200;
  }
  if (summary) {
    const v =
      summary.kind === 'impact' ? impactSummary(summary.ref, t) : summary.kind === 'tangle' ? tangleSummary(t) : null;
    if (v) {
      parts.push(v.html);
      t += v.items * 60 + 200;
    }
  }
  return { html: parts.join(''), settle: t };
}
