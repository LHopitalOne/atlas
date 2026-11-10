/**
 * Real maps embedded by the build (`node scripts/build.mjs --maps=key:spec.json,...`): an index of their keys and
 * labels, and each spec in its own script element, parsed only when that map is first shown.
 */
let INDEX = null;
const parsed = new Map();

/** [{key, label}] in the order given to the build; empty for builds without maps. */
export function mapList() {
  if (!INDEX) {
    const el = document.getElementById('mapIndex');
    INDEX = el ? JSON.parse(el.textContent) : [];
  }
  return INDEX;
}

/** Is `key` one of the embedded maps? */
export const isMap = key => mapList().some(m => m.key === key);

/** The spec of an embedded map. */
export function mapSpec(key) {
  if (!parsed.has(key)) parsed.set(key, JSON.parse(document.getElementById('map-' + key).textContent));
  return parsed.get(key);
}

/** The label of an embedded map, for buttons and messages. */
export const mapLabel = key => (mapList().find(m => m.key === key) || { label: key }).label;
