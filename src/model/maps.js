/**
 * Real maps embedded by the build (`node scripts/build.mjs --maps=key:spec.json,...`): an index of their keys and
 * labels, and each spec in its own script element, parsed only when that map is first shown. With --external-maps the
 * element is empty and names the spec's file in `data-src`, downloaded when that map is first shown.
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

/** The file a map is kept in (a build with --external-maps), or '' when it is in the page or already downloaded. */
export function mapSource(key) {
  const el = document.getElementById('map-' + key);
  return parsed.has(key) || !el ? '' : el.dataset.src || '';
}

/** Download a map kept in its own file; resolves at once for a map in the page. */
export async function loadMap(key, get = fetch) {
  const src = mapSource(key);
  if (!src) return;
  const res = await get(src);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`.trim());
  parsed.set(key, await res.json());
}

/** The spec of an embedded map (one kept in its own file: after loadMap). */
export function mapSpec(key) {
  if (!parsed.has(key)) parsed.set(key, JSON.parse(document.getElementById('map-' + key).textContent));
  return parsed.get(key);
}

/** The label of an embedded map, for buttons and messages. */
export const mapLabel = key => (mapList().find(m => m.key === key) || { label: key }).label;
