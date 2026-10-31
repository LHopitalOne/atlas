/**
 * Tuning constants. Everything that shapes how the map looks and behaves, in one place.
 * Sizes are CSS pixels unless noted; zoom is the camera scale k (screen px per world unit).
 */

/** Largest on-screen radius for service discs and endpoint dots (they stop growing past this, like map markers). */
export const SVC_MAX_PX = 26;
export const LEAF_MAX_PX = 6.5;

/** Label system (see render/labels.js). */
export const LABELS = {
  throttleMs: 250, // at most one placement pass this often while the camera moves
  settleMs: 150, // one more pass this long after the camera stops
  fadeInS: 0.2, // label fade-in, seconds
  fadeOutS: 0.14, // label fade-out, seconds (exits are faster than entrances)
  leafZoom: 2.1, // endpoint labels appear from this zoom
  focusLeafZoom: 0.85, // ...or from this zoom for the selection's endpoints
  caps: { repo: 120, domain: 200, service: 260, leaf: 320 }, // most labels placed per tier per pass
};

/** Camera flights (see app/camera.js). */
export const FLIGHT = { defaultMs: 450, introMs: 600, zoomButtonMs: 220 };
