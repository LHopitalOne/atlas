/** Text and number formatting. Safe in Node and the browser. */
const NF = new Intl.NumberFormat(
  typeof navigator !== 'undefined' && navigator.languages && navigator.languages.length
    ? navigator.languages
    : undefined,
);
export const esc = s =>
  String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
export const fmt = n => NF.format(n);
export const SANS = '"Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
export const MONO = '"Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace';
