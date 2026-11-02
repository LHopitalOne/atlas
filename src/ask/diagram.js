/**
 * Diagrams for answers. Pure.
 *
 * An answer that describes an order ends with a step line (before FOLLOWUPS):
 *   FLOW: n12 > n40 > n7 < n9                                  a route: > follows the call, < goes against it
 *   FLOW: Data=n1,n2 | Upload once=n4,n5 | Each frame=n9       stages in sequence, each with its items
 * The panel draws it as a vertical step line; toMermaid() turns it (or an answer's trail) into Mermaid text to copy.
 */

const LINK = /\s+([<>|])\s+/;

/**
 * Split the trailing control lines (FLOW:, FOLLOWUPS:) off an answer, in any order.
 * @returns {{body:string, followups:string[], flow:string|null}}
 */
export function splitControl(text) {
  let body = String(text),
    followups = [],
    flow = null,
    m;
  while ((m = body.match(/\n?[ \t]*(FLOW|FOLLOWUPS):[ \t]*([^\n]*)\s*$/i))) {
    if (m[1].toUpperCase() === 'FLOW') flow = flow ?? m[2].trim();
    else
      followups = m[2]
        .split('|')
        .map(s => s.trim())
        .filter(Boolean)
        .slice(0, 3);
    body = body.slice(0, m.index);
  }
  return { body, followups, flow };
}

/**
 * Parse a step line.
 * @param {string} line the text after "FLOW:"
 * @param {(ref:string)=>boolean} [valid] drops refs that point at nothing
 * @returns {{stops:{title:string, refs:string[]}[], links:string[]} | null} links[k] joins stops[k] and stops[k+1]
 */
export function parseFlow(line, valid = () => true) {
  if (!line) return null;
  const parts = line.split(LINK),
    stops = [],
    links = [];
  for (let k = 0; k < parts.length; k += 2) {
    const raw = parts[k].trim(),
      eq = raw.indexOf('=');
    const title = eq > 0 ? raw.slice(0, eq).trim() : '';
    const refs = (eq > 0 ? raw.slice(eq + 1) : raw)
      .split(',')
      .map(s => s.trim().replace(/^\[\[|\]\]$/g, ''))
      .filter(r => /^[ndr]\d+$/.test(r) && valid(r));
    if (!refs.length) continue;
    if (stops.length) links.push(parts[k - 1] || '|');
    stops.push({ title, refs });
  }
  return stops.length >= 2 ? { stops, links } : null;
}

const q = s => `"${String(s).replace(/"/g, '#quot;')}"`;

/**
 * Mermaid flowchart for an answer: from its step line, or else from its trail (hops between services).
 * @param {{flow?:object|null, hops?:{a:number,b:number,fwd:boolean}[], title?:string}} src
 * @param {(ref:string)=>string} nameOf
 * @returns {string}
 */
export function toMermaid({ flow = null, hops = [], title = '' }, nameOf) {
  const out = [];
  if (title) out.push(`%% ${title.replace(/\n/g, ' ')}`);
  if (flow) {
    const staged = flow.stops.some(s => s.title || s.refs.length > 1);
    out.push(staged ? 'flowchart TD' : 'flowchart LR');
    if (staged) {
      flow.stops.forEach((s, k) => {
        out.push(`  subgraph s${k}[${q(s.title || `Step ${k + 1}`)}]`);
        for (const r of s.refs) out.push(`    ${r}[${q(nameOf(r))}]`);
        out.push('  end');
      });
      flow.links.forEach((l, k) => out.push(`  s${k} --> s${k + 1}`));
    } else {
      flow.stops.forEach(s => out.push(`  ${s.refs[0]}[${q(nameOf(s.refs[0]))}]`));
      flow.links.forEach((l, k) => {
        const a = flow.stops[k].refs[0],
          b = flow.stops[k + 1].refs[0];
        out.push(l === '<' ? `  ${b} -->|calls| ${a}` : l === '>' ? `  ${a} -->|calls| ${b}` : `  ${a} --> ${b}`);
      });
    }
    return out.join('\n');
  }
  out.push('flowchart LR');
  const seen = new Set();
  for (const h of hops)
    for (const s of [h.a, h.b])
      if (!seen.has(s)) {
        seen.add(s);
        out.push(`  n${s}[${q(nameOf('n' + s))}]`);
      }
  for (const h of hops) out.push(h.fwd ? `  n${h.a} -->|calls| n${h.b}` : `  n${h.b} -->|calls| n${h.a}`);
  return out.join('\n');
}
