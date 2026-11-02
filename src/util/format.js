/** Text and number formatting. Safe in Node and the browser. */
/** Number formatter in the reader's language; an invalid language tag (e.g. "en-US@posix") falls back to the default. */
const NF = (() => {
  const langs = typeof navigator !== 'undefined' && navigator.languages ? [...navigator.languages] : [];
  for (const tags of [langs, langs.map(t => t.split(/[@.]/)[0]), undefined]) {
    try {
      return new Intl.NumberFormat(tags);
    } catch (_) {
      /* try the next option */
    }
  }
  return new Intl.NumberFormat();
})();
export const esc = s =>
  String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
export const fmt = n => NF.format(n);
export const SANS = '"Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
export const MONO = '"Geist Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace';
