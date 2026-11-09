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

/**
 * Ask Atlas engine. 'demo': simulated, animated answers (scripted rendering walkthrough, offline answers otherwise).
 * 'claude': ask Claude through the artifact sample capability (publish with capabilities {sample: {}}).
 */
export const ASK_ENGINE = 'demo';

/** Ask Atlas playback timing (ms). */
export const ASK_PLAYBACK = { think: 520, tick: 28, tokensPerTick: 2 };

/** HTTP links between repositories (see render/http.js and app/http.js). */
export const HTTP_PICK_PX = 6; // how close the pointer must be to a link's arc to hover or click it
export const HTTP_FIT_KMAX = 2.4; // closest zoom when flying to a link's two ends
export const HTTP_FIT_PAD = 0.2; // margin around a link when flying to it, as a share of its size
export const HTTP_ARC = {
  width: 1.5, // arc width at rest, px
  hotWidth: 2.6, // ...when selected, hovered or part of an impact view
  restAlpha: 0.8, // arc opacity at rest
  dimAlpha: 0.1, // ...while something else has the focus
  arrowPx: 6, // arrowhead length at the endpoint end
  endpointPx: 3.2, // endpoint marker radius, drawn at every zoom so endpoints show before their streets do
  flowSpeed: 0.11, // flow dots, screen px per ms
};
