/** Browser-only helpers. */
/** First element matching a CSS selector. */
export const $ = s => document.querySelector(s);
/** User prefers reduced motion (read once at load). */
export const reduceMotion = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
