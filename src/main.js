/**
 * Entry point. Checks browser support, wires every module to the DOM in a fixed order, then loads the first dataset.
 * Modules never do work at import time; everything starts here.
 */
import { loadDataset, mq, onTheme, resize } from './app/dataset.js';
import { glc, ov } from './dom.js';
import { requestRender } from './render/frame.js';
import { measure } from './render/canvas.js';
import { readTheme } from './render/theme.js';
import { init as init_ui_controls, syncThumb } from './ui/controls.js';
import { $ } from './util/dom.js';
import { initGL } from './render/gl.js';
import { setSelfSpec } from './model/self.js';
import { validateSpec } from './model/spec.js';
import { init as init_app_url, readHash } from './app/url.js';
import { init as init_app_pointer } from './app/pointer.js';
import { init as init_render_minimap } from './render/minimap.js';
import { init as init_ui_zoom } from './ui/zoom.js';
import { init as init_ui_where } from './ui/where.js';
import { init as init_ui_perf } from './ui/perf.js';
import { init as init_ui_legend } from './ui/legend.js';
import { init as init_ui_inspector } from './ui/inspector.js';
import { init as init_ui_attention } from './ui/attention.js';
import { init as init_ui_directions } from './ui/directions.js';
import { init as init_ui_search } from './ui/search.js';
import { init as init_app_keys } from './app/keys.js';

function showFallback(message) {
  const el = $('#nogl');
  if (message) el.firstElementChild.textContent = message;
  el.classList.add('on');
}

export function start() {
  if (!initGL()) return showFallback();
  if (!globalThis.d3 || !globalThis.d3.packSiblings)
    return showFallback('The layout library didn’t load. Check your connection, then reload.');
  init_app_pointer();
  init_render_minimap();
  init_ui_zoom();
  init_ui_where();
  init_ui_perf();
  init_ui_controls();
  init_ui_legend();
  init_ui_inspector();
  init_ui_attention();
  init_ui_directions();
  init_ui_search();
  init_app_keys();
  init_app_url();
  // boot
  new ResizeObserver(resize).observe(ov);
  mq.addEventListener ? mq.addEventListener('change', onTheme) : mq.addListener(onTheme);
  new MutationObserver(onTheme).observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
  document.fonts &&
    document.fonts.ready.then(() => {
      measure.clear();
      requestRender();
      syncThumb($('#seg'));
      syncThumb($('#scale'));
    });
  glc.addEventListener('webglcontextlost', e => {
    e.preventDefault();
    $('#nogl').firstElementChild.textContent = 'The graphics context was lost. Reload the page to restore the map.';
    $('#nogl').classList.add('on');
  });
  readTheme();
  if (matchMedia('(max-width:760px), (max-height:720px)').matches) $('#legend').open = false;
  resize();
  const first = readHash();
  loadDataset(first.n, location.hash.length > 1 ? first : null);
}

/**
 * Public API, available as `window.Atlas` in the built page.
 * Show any graph: validates it (see docs/GRAPH_SPEC.md), replaces the embedded "Self" graph and switches to it.
 * @param {object} spec graph spec
 * @throws {Error} listing what is wrong with the spec
 */
export function loadGraph(spec) {
  const problems = validateSpec(spec);
  if (problems.length) throw new Error('Invalid graph spec:\n- ' + problems.join('\n- '));
  setSelfSpec(spec);
  const btn = $('#scale [data-v="self"]');
  if (btn) btn.textContent = (spec.meta && spec.meta.label) || 'Graph';
  loadDataset('self');
}

start();
