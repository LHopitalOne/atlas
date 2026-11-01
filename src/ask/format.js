/**
 * Answers into safe HTML: paragraphs, lists, `code`, **bold**, and citations. A citation is a reference in double
 * brackets, `[[n12]]`, which becomes a numbered chip for that map item; a final line `FOLLOWUPS: a | b | c` becomes
 * suggested follow-up questions. Pure.
 */
import { esc } from '../util/format.js';

const CITE = /\[\[([ndr]\d+)\]\]/g;

/** Split off the follow-up line. */
export function splitFollowups(text) {
  const m = String(text).match(/\n?\s*FOLLOWUPS:\s*(.+)\s*$/i);
  if (!m) return { body: String(text), followups: [] };
  return {
    body: String(text).slice(0, m.index),
    followups: m[1]
      .split('|')
      .map(s => s.trim())
      .filter(Boolean)
      .slice(0, 3),
  };
}

/**
 * @param {string} text answer text (possibly still streaming)
 * @param {(ref:string)=>boolean} isValid drops citations that point at nothing
 * @param {(ref:string)=>string} nameOf tooltip text for a chip
 * @returns {{html:string, refs:string[], followups:string[]}} refs in citation order (chip n = refs[n-1])
 */
export function renderAnswer(text, isValid, nameOf, streaming = false) {
  let { body, followups } = splitFollowups(text);
  if (streaming) body = body.replace(/\[\[[^\]]*$/, '').replace(/\n?\s*FOLLOWUPS:[^\n]*$/i, '');
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
  const blocks = body.trim().split(/\n{2,}/),
    out = [];
  for (const b of blocks) {
    const lines = b.split('\n');
    if (lines.every(l => /^\s*([-*]|\d+\.)\s+/.test(l))) {
      const ordered = /^\s*\d+\./.test(lines[0]);
      out.push(
        `<${ordered ? 'ol' : 'ul'}>${lines.map(l => `<li>${inline(l.replace(/^\s*([-*]|\d+\.)\s+/, ''))}</li>`).join('')}</${ordered ? 'ol' : 'ul'}>`,
      );
    } else out.push(`<p>${lines.map(inline).join('<br>')}</p>`);
  }
  return { html: out.join(''), refs, followups };
}
