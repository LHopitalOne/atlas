/**
 * Simulated answers for the prototype: a scripted walkthrough for "how do we render the graph?" (Atlas's real pipeline,
 * cited with real functions from the Self map) and, for anything else, the offline answerer. Each script is played by
 * the panel with timing: thinking, steps one by one (each ringing an item on the map), then the text streaming in.
 * Pure: returns { steps: [{label, ref?, ms}], text, note? }.
 */
import { resolve } from './tools.js';
import { answerLocally } from './local.js';

/** Questions the rendering walkthrough answers. */
export const RENDER_QUESTION = /\b(render(s|ed|ing)?|draw(s|n|ing)?|pipeline|webgl|gpu|end[- ]to[- ]end)\b/i;

/** Suggested first question in an empty conversation. */
export const DEMO_QUESTION = 'How are we rendering the graph? The end-to-end flow';

const RENDER_ANSWER = `Rendering is a one-time build per map, followed by a cheap frame loop that only runs when something changes.

1. **Data.** {{build}} generates a demo map, or {{buildSpec}} loads a real one. {{finish}} indexes it and lays it out: circle packing, endpoint rings, territory outlines.
2. **Upload once.** {{buildScene}} turns the map into GPU layers (curves, nodes, territory fills) and {{upload}} sends them to WebGL2, which {{initGL}} set up.
3. **Render on change.** Every interaction calls {{requestRender}}. {{frame}} runs on the next animation frame and stops when nothing moves.
4. **Each frame.** {{render}} picks the level of detail with {{lod}} (repositories, domains, services, endpoints), then draws {{drawFill}}, {{drawEdges}} and {{drawNodes}}.
5. **On top.** {{drawOverlay}} paints the 2D layer: flow dots, rings, pins and labels. {{drawLabels}} shows the labels that {{placeLabels}} placed without collisions.
6. **After drawing.** UI that follows the camera, such as the breadcrumb and zoom slider, subscribes with {{onFrameDrawn}}.

FOLLOWUPS: Why does it only render on change? | How are labels placed? | What breaks if I change buildScene?`;

const RENDER_STEPS = [
  { label: 'Searched the index for “render”', ms: 520 },
  { label: 'Described frame', ref: 'frame', ms: 460 },
  { label: 'Described render', ref: 'render', ms: 460 },
  { label: 'Traced requestRender → frame → render', ref: 'requestRender', ms: 520 },
  { label: 'Read the code of buildScene (live, not stored)', ref: 'buildScene', ms: 640 },
  { label: 'Checked how labels are placed', ref: 'placeLabels', ms: 460 },
];

const svcRef = (g, name) => {
  const e = resolve(g, name);
  return e && e.t === 'n' ? `n${e.id}` : null;
};

/** The rendering walkthrough, cited against the current map (names not on this map stay as plain code). */
export function renderingScript(g) {
  let missing = 0;
  const text = RENDER_ANSWER.replace(/\{\{(\w+)\}\}/g, (_, name) => {
    const ref = svcRef(g, name);
    if (!ref) missing++;
    return ref ? `${name} [[${ref}]]` : `\`${name}\``;
  });
  return {
    steps: RENDER_STEPS.map(s => ({ ...s, ref: s.ref ? svcRef(g, s.ref) : null })),
    text,
    note: missing ? 'This walkthrough is about Atlas’s own code. Switch to Self to see it on the map.' : '',
  };
}

/** A script for any question: the rendering walkthrough, or the offline answer with its lookups as steps. */
export function scriptFor(g, q, { context = null } = {}) {
  if (RENDER_QUESTION.test(q)) return renderingScript(g);
  const steps = [];
  const text = answerLocally(g, q, { context, onStep: label => steps.push({ label, ms: 440 }) });
  return { steps, text, note: '' };
}
