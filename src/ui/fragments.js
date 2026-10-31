/**
 * Small HTML fragments shared by panels (status dots, badges, pills, icons). Callers escape all dynamic text with esc().
 */
import { store } from '../state.js';
import { KCLS, STATUS } from '../model/vocab.js';
import { css, nodeCol, theme } from '../render/theme.js';
import { fmt } from '../util/format.js';

export const nameAttrs = 'translate="no"';
export const dotHTML = i =>
  `<span class="g ${KCLS[i < store.G.S ? 0 : store.G.KND[i]]}" style="--c:${css(nodeCol(i))}" aria-hidden="true"></span>`;
export const BCLS = ['badge-secondary', 'badge-warning', 'badge-destructive', 'badge-inferred'];
export const pills = c => {
  let h = '';
  for (let s = 0; s < 4; s++)
    if (c[s])
      h += `<span class="badge ${BCLS[s]}" title="${STATUS[s]}"><span class="sr-only">${STATUS[s]} </span>${fmt(c[s])}</span>`;
  return h;
};
export function healthBlock(c) {
  const t = c[0] + c[1] + c[2] + c[3];
  if (!t) return '';
  const cols = [css(theme.text, 0.3), css(theme.st[1]), css(theme.st[2]), css(theme.st[3])];
  let bar = '',
    leg = '';
  for (let s = 0; s < 4; s++)
    if (c[s]) {
      bar += `<i style="--c:${cols[s]};flex:${c[s]}"></i>`;
      leg += `<span><i style="--c:${cols[s]}"></i>${fmt(c[s])} ${STATUS[s].toLowerCase()}</span>`;
    }
  return `<div class="hbar" aria-hidden="true">${bar}</div><div class="hleg">${leg}</div>`;
}
export const moreBtn = (key, total, cap) =>
  total > cap
    ? `<button class="btn btn-ghost btn-sm more" data-more="${key}">Show ${fmt(Math.min(total - cap, 200))} more</button>`
    : '';
export const ICON_X = `<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;
