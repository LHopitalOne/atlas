/**
 * HTTP links on the map: picking a link's arc, opening a link's proof (store.linkId), and the impact view that lights
 * up everything in other repositories calling an endpoint, a file or a repository (store.httpImpact: 'n<id>' or 'r<id>').
 */
import { cam, store } from '../state.js';
import { fitBox, fitNodes, flyTo, flyToTerr } from './camera.js';
import { updateFocus } from './focus.js';
import { writeHash } from './url.js';
import { closeSource } from '../ui/code-view.js';
import { announce } from '../ui/feedback.js';
import { openLinkInspector, openInspector } from '../ui/inspector.js';
import { arcCtrl, arcDistance, httpImpact } from '../model/http.js';
import { HTTP_FIT_KMAX, HTTP_FIT_PAD, HTTP_PICK_PX } from '../config.js';

/** The HTTP link group whose arc passes within tolPx of a screen point, or null. */
export function pickLink(px, py, tolPx = HTTP_PICK_PX) {
  const g = store.G,
    H = g && g.http;
  if (!H) return null;
  const SX = x => x * cam.k + cam.x,
    SY = y => y * cam.k + cam.y;
  let best = -1,
    bd = tolPx;
  H.groups.forEach((gr, i) => {
    const x0 = SX(g.PX[gr.from]),
      y0 = SY(g.PY[gr.from]),
      x1 = SX(g.PX[gr.to]),
      y1 = SY(g.PY[gr.to]);
    const d = arcDistance(px, py, x0, y0, x1, y1);
    if (d < bd) {
      bd = d;
      best = i;
    }
  });
  return best >= 0 ? { t: 'h', id: best } : null;
}

/** A view that holds a link's two ends and the bulge of its arc, so the whole line is on screen. */
function fitLink(g, gr) {
  const xs = [],
    ys = [];
  for (const i of [gr.from, gr.to, g.own(gr.from), g.own(gr.to)]) {
    xs.push(g.PX[i] - g.PR[i], g.PX[i] + g.PR[i]);
    ys.push(g.PY[i] - g.PR[i], g.PY[i] + g.PR[i]);
  }
  const x0 = g.PX[gr.from],
    y0 = g.PY[gr.from],
    x1 = g.PX[gr.to],
    y1 = g.PY[gr.to],
    [cx, cy] = arcCtrl(x0, y0, x1, y1);
  xs.push(0.25 * x0 + 0.5 * cx + 0.25 * x1);
  ys.push(0.25 * y0 + 0.5 * cy + 0.25 * y1);
  const padX = (Math.max(...xs) - Math.min(...xs)) * HTTP_FIT_PAD,
    padY = (Math.max(...ys) - Math.min(...ys)) * HTTP_FIT_PAD;
  return fitBox(
    Math.min(...xs) - padX,
    Math.min(...ys) - padY,
    Math.max(...xs) + padX,
    Math.max(...ys) + padY,
    store.KMIN,
    HTTP_FIT_KMAX,
  );
}

/** Show the proof of link group gid in the inspector and light up its two ends. */
export function openLink(gid, via) {
  const g = store.G,
    gr = g.http.groups[gid];
  closeSource(false);
  store.selectedId = -1;
  store.impactId = -1;
  store.httpImpact = '';
  store.linkId = gid;
  store.hover = null;
  store.placeDirty = true;
  updateFocus();
  openLinkInspector(gid);
  flyTo(fitLink(g, gr));
  const l = g.http.links[gr.links[0]];
  announce(`Link ${l.method} ${l.path} from ${g.repoName[l.call.repo]} to ${g.repoName[l.route.repo]}.`);
  if (via === 'list' || via === 'map')
    requestAnimationFrame(() => {
      const t = document.getElementById('insTitle');
      if (t) t.focus({ preventScroll: true });
    });
  writeHash();
}

/** Toggle the impact view for an endpoint or service ('n<id>') or a repository ('r<id>'). */
export function toggleHttpImpact(key) {
  const g = store.G,
    on = store.httpImpact !== key;
  store.httpImpact = on ? key : '';
  store.focusId = -1;
  updateFocus();
  const target = { t: key[0], id: +key.slice(1) },
    im = httpImpact(g, g.http, target);
  if (target.t === 'n' && store.selectedId === target.id) openInspector(target.id);
  for (const b of document.querySelectorAll('[data-http-impact]')) {
    const pressed = b.dataset.httpImpact === store.httpImpact;
    b.setAttribute('aria-pressed', String(pressed));
    b.textContent = pressed ? 'Hide on map' : b.dataset.label || 'Show on map';
  }
  if (on && im.groups.length) {
    const ends = im.groups.flatMap(i => [g.http.groups[i].from, g.http.groups[i].to]);
    flyTo(fitNodes([...ends, ...ends.map(g.own)], 1.6));
  } else if (on && target.t === 'r') flyToTerr('r', target.id);
  const name = target.t === 'r' ? g.repoName[target.id] : g.name(target.id);
  announce(on ? `Showing what calls ${name} from other repositories.` : 'Impact view off.');
}

/** Close the impact view if it is showing a repository (opening something else replaces it). */
export function clearRepoImpact() {
  if (store.httpImpact[0] === 'r') store.httpImpact = '';
}
