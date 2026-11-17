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
 * 'openrouter': ask ASK_MODEL on OpenRouter, through `atlas serve`'s local proxy (it holds OPENROUTER_API_KEY) or,
 * on any other page, with a key the viewer gives once (kept in that browser tab only).
 */
export const ASK_ENGINE = 'openrouter';
export const ASK_MODEL = 'meta/muse-ember';
export const ASK_LLM = {
  maxSteps: 8, // tool rounds before the model must answer
  maxToolChars: 12000, // a tool result is cut to this many characters before it goes back to the model
  maxTokens: 2500, // per request, reasoning and answer together
  proxy: './api/llm', // `atlas serve` forwards <proxy>/chat/completions to OpenRouter with its key
  direct: 'https://openrouter.ai/api/v1',
  keyStore: 'atlas.openrouterKey', // sessionStorage key for a key the viewer pasted
};

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
  withinAlpha: 0.22, // ...for links inside one repository (a frontend calling its own API), which are many
  dimAlpha: 0.1, // ...while something else has the focus
  arrowPx: 6, // arrowhead length at the endpoint end
  endpointPx: 3.2, // endpoint marker radius, drawn at every zoom so endpoints show before their streets do
  flowSpeed: 0.11, // flow dots, screen px per ms
};

/** Welcome tour on demo pages, built with --tour (see ui/tour.js). */
export const TOUR = {
  storeKey: 'atlas.tourDone', // localStorage: set once the tour is finished or skipped
  startMs: 700, // after the first map appears (its intro flight is FLIGHT.introMs)
  settleMs: 700, // after a step changes, follow the target every frame this long (panels slide in)
  stillMs: 50, // the card appears once the lit parts have not moved for this long (or settleMs is up)
  fadeMs: 180, // the dim layer fades out this long when the tour closes
  pad: 6, // spotlight margin around the target, px
  radius: 14, // corner radius of a lit part, px
  linkPad: 28, // ...around the map's links, which bulge past their ends
  minHole: 160, // smallest spotlight around the map's links, px
  edge: 12, // the card keeps this far from the window's edges, px
  gap: 12, // between the spotlight and the card, px
  top: 64, // a card in a top corner starts below the toolbar, px
  phone: '(max-width:760px)', // the card becomes a sheet at the bottom (or the top, when the target is low)
  // the sample question, per map: a route across three repositories, so the answer draws it as a diagram
  ask: {
    sentry: 'How does relay reach snuba?',
    openedx: 'How does frontend-app-learning reach credentials?',
  },
  askAny: 'How does {from} reach {to}?', // other maps with links: the busiest pair of repositories
  askPlain: 'Are there any dependency cycles?', // maps without links
};
