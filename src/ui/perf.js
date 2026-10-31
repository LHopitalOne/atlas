/**
 * Performance readout in the map controls: frame time and GPU instance count (build time and memory in the tooltip).
 */
import { store } from '../state.js';
import { PERF } from '../dom.js';
import { onFrameEnd } from '../render/frame.js';
import { $ } from '../util/dom.js';
import { fmt } from '../util/format.js';

let LIVE = null;
let PMS = null;
let PDR = null;
let idleTO = 0;
export function renderPerf() {
  PERF.title = `Built in ${fmt(Math.round(store.buildInfo.t))} ms, ${(store.buildInfo.bytes / 1048576).toFixed(1)} MB in memory`;
  PERF.innerHTML = `<span class="live" id="live" aria-hidden="true"></span><span><b id="pms">0.0</b> ms/frame</span><span class="r"><b id="pdr">0</b> on GPU</span>`;
  LIVE = $('#live');
  PMS = $('#pms');
  PDR = $('#pdr');
}
export function perfTick(now) {
  if (now - store.perfAt > 200) {
    store.perfAt = now;
    PMS.textContent = store.cpuMs.toFixed(2);
    PDR.textContent = store.drawn >= 1e3 ? fmt(Math.round(store.drawn / 1e3)) + 'k' : fmt(Math.round(store.drawn));
  }
  LIVE.classList.add('on');
  clearTimeout(idleTO);
  idleTO = setTimeout(() => LIVE.classList.remove('on'), 300);
}

/** Subscribe the readout to the frame loop. Called once from main.js. */
export function init() {
  onFrameEnd(perfTick);
}
