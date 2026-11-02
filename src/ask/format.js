/**
 * Answers into safe HTML: paragraphs, lists, `code`, **bold**, and citations. A citation is a reference in double
 * brackets, `[[n12]]`, which becomes a numbered chip for that map item; a final line `FOLLOWUPS: a | b | c` becomes
 * suggested follow-up questions. Pure.
 */
import { esc } from '../util/format.js';
import { parseFlow, splitControl } from './diagram.js';

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
  const refs = [];
  const inline = s =>
    esc(s)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(CITE, (_, ref) => {
        if (!isValid(ref)) return '';
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
    const flushPara = () => {
      if (para.length) out.push(`<p>${para.map(inline).join('<br>')}</p>`);
      para = [];
    };
    const flushList = () => {
      if (list.length)
        out.push(
          `<${ordered ? 'ol' : 'ul'}>${list.map(l => `<li>${inline(l)}</li>`).join('')}</${ordered ? 'ol' : 'ul'}>`,
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
  return { html: out.join(''), refs, followups, flow: streaming ? null : parseFlow(flow, isValid) };
}
