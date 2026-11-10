/**
 * Pointer, wheel, pinch and keyboard input on the map canvas: hover, click to select, drag to pan, keyboard reticle.
 */
import { cam, route, store } from '../state.js';
import { camFor, fitNodes, flyTo, flyToTerr, viewCenter, zoomAt } from './camera.js';
import { same, setHover } from './focus.js';
import { setRouteEnd } from './route.js';
import { describe, deselect, pick, select } from './selection.js';
import { openLink } from './http.js';
import { ov, WHERE } from '../dom.js';
import { requestRender } from '../render/frame.js';
import { announce } from '../ui/feedback.js';

const ptrs = new Map();
let drag = null;
let pinch = null;
const offHitAt = (x, y) => store.offHits.find(o => x >= o.x0 && x <= o.x1 && y >= o.y0 && y <= o.y1);
const endPtr = e => {
  ptrs.delete(e.pointerId);
  if (drag && !drag.moved && e.type === 'pointerup') {
    const oh = offHitAt(e.offsetX, e.offsetY);
    if (oh) flyTo(fitNodes([store.selectedId, ...oh.ids], 2.4));
    else {
      const h = pick(e.offsetX, e.offsetY, e.pointerType === 'touch' ? 14 : 7);
      if (!h) deselect();
      else if (h.t === 'n') select(h.id, 'map');
      else if (h.t === 'h') openLink(h.id, 'map');
      else if (route.picking) setRouteEnd(route.picking, { t: h.t, id: h.id });
      else {
        deselect();
        flyToTerr(h.t, h.id);
      }
    }
  }
  if (ptrs.size < 2) pinch = null;
  if (!ptrs.size) {
    drag = null;
    ov.classList.remove('dragging');
  }
};
// keyboard: the map is a focusable region with a centre reticle
export function keyHover() {
  if (!store.G) return;
  const c = viewCenter();
  const h = pick(c.x, c.y, 18);
  if (!same(h, store.hover)) {
    setHover(h, true);
    announce(
      h
        ? describe(h) + '. Press Enter to open.'
        : `${WHERE.textContent.trim()}. Nothing under the marker; press Enter to zoom in.`,
    );
  }
}
export function panBy(dx, dy) {
  store.anim = null;
  cam.x += dx;
  cam.y += dy;
  requestRender();
  if (store.kbdMap) keyHover();
}

/** Wire this module to the DOM. Called once from main.js. */
export function init() {
  ov.addEventListener('pointerdown', e => {
    ov.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, { x: e.offsetX, y: e.offsetY });
    store.anim = null;
    store.kbdMap = false;
    if (ptrs.size === 1) drag = { x: e.offsetX, y: e.offsetY, cx: cam.x, cy: cam.y, moved: false };
    else if (ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), k: cam.k };
      drag = null;
    }
  });
  ov.addEventListener('pointermove', e => {
    if (!store.G) return;
    if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, { x: e.offsetX, y: e.offsetY });
    if (pinch && ptrs.size === 2) {
      const [a, b] = [...ptrs.values()];
      zoomAt((a.x + b.x) / 2, (a.y + b.y) / 2, (pinch.k * Math.hypot(a.x - b.x, a.y - b.y)) / pinch.d / cam.k);
      return;
    }
    if (drag) {
      const dx = e.offsetX - drag.x,
        dy = e.offsetY - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) > 3) {
        drag.moved = true;
        ov.classList.add('dragging');
        setHover(null, true);
      }
      if (drag.moved) {
        cam.x = drag.cx + dx;
        cam.y = drag.cy + dy;
        requestRender();
      }
      return;
    }
    if (e.pointerType === 'touch') return;
    const oh = offHitAt(e.offsetX, e.offsetY),
      h = oh ? null : pick(e.offsetX, e.offsetY);
    ov.classList.toggle('pointing', !!(h || oh));
    setHover(h);
  });
  ov.addEventListener('pointerup', endPtr);
  ov.addEventListener('pointercancel', endPtr);
  ov.addEventListener('pointerleave', () => {
    if (!drag && store.hover) {
      ov.classList.remove('pointing');
      setHover(null);
    }
  });
  ov.addEventListener(
    'wheel',
    e => {
      e.preventDefault();
      zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * (e.ctrlKey ? 0.012 : 0.0018)));
    },
    { passive: false },
  );
  ov.addEventListener('dblclick', e => {
    const wx = (e.offsetX - cam.x) / cam.k,
      wy = (e.offsetY - cam.y) / cam.k;
    flyTo(camFor(wx, wy, Math.min(store.KMAX, cam.k * 2.4)), 450);
  });
  ov.addEventListener('focus', () => {
    store.kbdMap = ov.matches(':focus-visible');
    if (store.kbdMap) keyHover();
    requestRender();
  });
  ov.addEventListener('blur', () => {
    store.kbdMap = false;
    requestRender();
  });
  ov.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (!store.hover) {
        const c = viewCenter();
        flyTo(camFor((c.x - cam.x) / cam.k, (c.y - cam.y) / cam.k, Math.min(store.KMAX, cam.k * 2)));
        keyHover();
      } else if (store.hover.t === 'n') select(store.hover.id, 'map');
      else if (store.hover.t === 'h') openLink(store.hover.id, 'map');
      else {
        flyToTerr(store.hover.t, store.hover.id);
        requestAnimationFrame(keyHover);
      }
    }
  });
}
