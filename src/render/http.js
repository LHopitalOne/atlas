/**
 * HTTP links on the overlay: one arc per caller-to-endpoint link, coloured by how it is proven, with an arrowhead at
 * the endpoint and a marker on every endpoint, at every zoom. Selected, hovered and impact links are drawn
 * stronger, with dots flowing in call direction; a hovered link gets a tooltip with its method, path and proof.
 */
import { store } from '../state.js';
import { HTTP_ARC } from '../config.js';
import { oc } from '../dom.js';
import { arcCtrl, groupsFrom, groupsInto, httpImpact, PROOF } from '../model/http.js';
import { css, theme } from './theme.js';
import { LC, rrect, tw } from './canvas.js';
import { reduceMotion } from '../util/dom.js';
import { MONO, SANS } from '../util/format.js';

/** Colour and dash of an arc for a proof. */
function arcStyle(proof) {
  if (proof === 'scip' || proof === 'syntax') return [theme.proof, null];
  if (proof === 'inferred') return [theme.st[3], [5, 4]];
  if (proof === 'ambiguous') return [theme.st[1], [5, 4]];
  if (proof === 'contradicted') return [theme.st[2], [2, 3]];
  return [theme.text, null];
}

/** Link groups to draw strongly: the open link, the hovered one, the selection's own, an impact view's. */
export function hotGroups(g) {
  const H = g.http,
    hot = new Set();
  if (store.linkId >= 0) hot.add(store.linkId);
  if (store.hover && store.hover.t === 'h') hot.add(store.hover.id);
  if (store.selectedId >= 0) {
    const n = { t: 'n', id: store.selectedId };
    for (const i of [...groupsFrom(g, H, store.selectedId), ...groupsInto(g, H, n)]) hot.add(i);
  }
  if (store.httpImpact) {
    const t = { t: store.httpImpact[0], id: +store.httpImpact.slice(1) };
    for (const i of httpImpact(g, H, t).groups) hot.add(i);
  }
  return hot;
}

/** Draw every HTTP link. */
export function drawHttp(fx) {
  const { g, I, now, SX, SY, on } = fx,
    H = g.http;
  if (!H || !H.groups.length) return;
  const hot = hotGroups(g),
    focused = store.dimT > 0.02 && (hot.size > 0 || store.focusId >= 0),
    order = H.groups.map((_, i) => i).sort((a, b) => hot.has(a) - hot.has(b));
  for (const i of order) {
    const gr = H.groups[i],
      isHot = hot.has(i),
      x0 = SX(g.PX[gr.from]),
      y0 = SY(g.PY[gr.from]),
      x1 = SX(g.PX[gr.to]),
      y1 = SY(g.PY[gr.to]);
    if (!on(x0, y0, 4000) && !on(x1, y1, 4000)) continue;
    const [cx, cy] = arcCtrl(x0, y0, x1, y1),
      [col, dash] = arcStyle(gr.proof),
      rest = gr.within ? HTTP_ARC.withinAlpha : HTTP_ARC.restAlpha,
      a = isHot ? 1 : focused ? HTTP_ARC.dimAlpha + (rest - HTTP_ARC.dimAlpha) * (1 - store.dimT) : rest;
    oc.globalAlpha = a * I;
    oc.strokeStyle = css(col);
    oc.lineWidth = isHot ? HTTP_ARC.hotWidth : HTTP_ARC.width;
    oc.setLineDash(dash || []);
    oc.beginPath();
    oc.moveTo(x0, y0);
    oc.quadraticCurveTo(cx, cy, x1, y1);
    oc.stroke();
    oc.setLineDash([]);
    arrowHead(x1, y1, cx, cy, col);
    endpointMark(x1, y1, col);
    if (isHot && !reduceMotion) flowDots(x0, y0, cx, cy, x1, y1, now, col, on);
  }
  oc.globalAlpha = 1;
}

function arrowHead(x1, y1, cx, cy, col) {
  const ang = Math.atan2(y1 - cy, x1 - cx),
    L = HTTP_ARC.arrowPx,
    back = HTTP_ARC.endpointPx + 1.5;
  oc.save();
  oc.translate(x1 - Math.cos(ang) * back, y1 - Math.sin(ang) * back);
  oc.rotate(ang);
  oc.beginPath();
  oc.moveTo(0, 0);
  oc.lineTo(-L, -L * 0.55);
  oc.lineTo(-L, L * 0.55);
  oc.closePath();
  oc.fillStyle = css(col);
  oc.fill();
  oc.restore();
}

function endpointMark(x, y, col) {
  const r = HTTP_ARC.endpointPx;
  oc.beginPath();
  oc.moveTo(x, y - r * 1.25);
  oc.lineTo(x + r * 1.25, y);
  oc.lineTo(x, y + r * 1.25);
  oc.lineTo(x - r * 1.25, y);
  oc.closePath();
  oc.fillStyle = css(theme.halo);
  oc.fill();
  oc.lineWidth = 1.4;
  oc.strokeStyle = css(col);
  oc.stroke();
}

function flowDots(x0, y0, cx, cy, x1, y1, now, col, on) {
  const L = Math.hypot(x1 - x0, y1 - y0),
    n = Math.max(1, Math.min(6, Math.round(L / 110)));
  oc.fillStyle = css(col);
  for (let q = 0; q < n; q++) {
    const t = ((now * HTTP_ARC.flowSpeed) / Math.max(L, 1) + q / n) % 1,
      u = 1 - t,
      x = u * u * x0 + 2 * u * t * cx + t * t * x1,
      y = u * u * y0 + 2 * u * t * cy + t * t * y1;
    if (!on(x, y, 6)) continue;
    const ga = oc.globalAlpha;
    oc.globalAlpha = ga * Math.min(1, Math.sin(Math.PI * t) * 2.2);
    oc.beginPath();
    oc.arc(x, y, 2.4, 0, Math.PI * 2);
    oc.fill();
    oc.globalAlpha = ga;
  }
}

/** Tooltip for the hovered link: method and path, the repositories it joins, and its proof. */
export function drawHttpTip(fx) {
  const { g, SX, SY } = fx,
    H = g.http;
  if (!H || !store.hover || store.hover.t !== 'h') return;
  const gr = H.groups[store.hover.id],
    l = H.links[gr.links[0]],
    x0 = SX(g.PX[gr.from]),
    y0 = SY(g.PY[gr.from]),
    x1 = SX(g.PX[gr.to]),
    y1 = SY(g.PY[gr.to]),
    [cx, cy] = arcCtrl(x0, y0, x1, y1),
    mx = 0.25 * x0 + 0.5 * cx + 0.25 * x1,
    my = 0.25 * y0 + 0.5 * cy + 0.25 * y1;
  const top = `${l.method} ${l.path}`,
    more = gr.links.length > 1 ? ` · ${gr.links.length} call sites` : '',
    sub = `${g.repoName[l.call.repo]} → ${g.repoName[l.route.repo]} · ${PROOF[gr.proof].label}${more}`,
    fTop = '500 12px ' + MONO,
    fSub = '400 11.5px ' + SANS,
    w = Math.max(tw(fTop, top), tw(fSub, sub)) + 20,
    h = 42,
    x = Math.min(Math.max(8, mx - w / 2), store.W - w - 8),
    y = Math.max(8, my - h - 12);
  oc.globalAlpha = 1;
  rrect(x, y, w, h, 8);
  oc.fillStyle = css(theme.halo);
  oc.fill();
  oc.lineWidth = 1;
  oc.strokeStyle = css(theme.text, 0.22);
  oc.stroke();
  oc.textAlign = 'left';
  oc.fillStyle = css(theme.text);
  oc.font = fTop;
  oc.fillText(top, x + 10, y + 14);
  oc.fillStyle = css(theme.muted);
  oc.font = fSub;
  oc.fillText(sub, x + 10, y + 30);
  LC.fits(x, y, x + w, y + h, true);
}
