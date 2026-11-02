/**
 * Answers into safe HTML: paragraphs, lists, `code`, **bold**, and citations. A citation is a reference in double
 * brackets, `[[n12]]`, which becomes a numbered chip for that map item; a final line `FOLLOWUPS: a | b | c` becomes
 * suggested follow-up questions. Pure.
 */
import { esc } from '../util/format.js';
import { parseFlow, splitControl } from './diagram.js';

/** The step line's own path: a route as one group; stages joined last-to-first, stage to stage. */
function flowGroups(flow) {
  if (!flow) return [];
  if (flow.stops.every(s => !s.title && s.refs.length === 1)) return [flow.stops.map(s => s.refs[0])];
  const out = [];
  for (let k = 1; k < flow.stops.length; k++) out.push([flow.stops[k - 1].refs.at(-1), flow.stops[k].refs[0]]);
  return out;
}

const CITE = /\[\[([ndr]\d+)\]\]/g;

/** Split off the follow-up line (kept for callers that only need follow-ups). */
export function splitFollowups(text) {
  const { body, followups } = splitControl(text);
  return { body, followups };
}

/**
 * @param {string} text answer text (possibly still streaming)
 * @param {(ref:string)=>boolean} isValid drops citations that point at nothing
 * @param {(ref:string)=>string} nameOf tooltip text for a chip
 * @returns {{html:string, refs:string[], followups:string[], flow:object|null}} refs in citation order (chip n = refs[n-1])
 */
export function renderAnswer(text, isValid, nameOf, streaming = false) {
  let { body, followups, flow } = splitControl(text);
  // while streaming, hide a half-written citation or control line
  if (streaming)
    body = body
      .replace(/\[\[[^\]]*$/, '')
      .replace(/\n?[ \t]*(FOLLOWUPS|FLOW):[^\n]*$/i, '')
      .replace(/\n[ \t]*F[LOWUPS]{0,8}$/i, '');
  const refs = [],
    groups = [];
  let group = [];
  const inline = s =>
    esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(CITE, (_, ref) => {
        if (!isValid(ref)) return '';
        group.push(ref);
        let n = refs.indexOf(ref);
        if (n < 0) {
          refs.push(ref);
          n = refs.length - 1;
        }
        return `<button class="cite" data-ref="${ref}" title="${esc(nameOf(ref))}" aria-label="Source ${n + 1}: ${esc(nameOf(ref))}">${n + 1}</button>`;
      });
  // blocks are separated by blank lines; inside a block, runs of list items become a list and other lines a paragraph
  const out = [],
    item = /^\s*([-*]|\d+\.)\s+/;
  for (const block of body.trim().split(/\n{2,}/)) {
    let para = [],
      list = [],
      ordered = false;
    const close = () => {
      if (group.length) groups.push(group);
      group = [];
    };
    const flushPara = () => {
      if (para.length) out.push(`<p>${para.map(inline).join('<br>')}</p>`);
      para = [];
      close();
    };
    const flushList = () => {
      if (list.length)
        out.push(
          `<${ordered ? 'ol' : 'ul'}>${list
            .map(l => {
              const li = `<li>${inline(l)}</li>`;
              close();
              return li;
            })
            .join('')}</${ordered ? 'ol' : 'ul'}>`,
        );
      list = [];
    };
    for (const line of block.split('\n')) {
      if (item.test(line)) {
        if (!list.length) {
          flushPara();
          ordered = /^\s*\d+\./.test(line);
        }
        list.push(line.replace(item, ''));
      } else {
        flushList();
        para.push(line);
      }
    }
    flushPara();
    flushList();
  }
  const parsed = streaming ? null : parseFlow(flow, isValid);
  return { html: out.join(''), refs, groups: groups.concat(flowGroups(parsed)), followups, flow: parsed };
}
