/**
 * Frame loop: renders only when something changes. Chooses the level of detail from zoom (repos, domains,
 * services, endpoints), draws the GPU layers, then the 2D overlay, then runs the frame hooks.
 */
import { cam, stOn, store } from '../state.js';
import { stepAnim } from '../app/camera.js';
import { ASK_FOCUS, clearFocus, ROUTE_FOCUS, routeActive } from '../app/focus.js';
import { LEAF_MAX_PX, SVC_MAX_PX } from '../config.js';
import { glc } from '../dom.js';
import { gl, LY, P_BG, P_EDGE, P_FILL, P_NODE } from './gl.js';
import { drawMinimap } from './minimap.js';
import { drawOverlay } from './overlay.js';
import { theme } from './theme.js';
import { reduceMotion } from '../util/dom.js';
import { clamp, easeOut, sstep } from '../util/math.js';

/**
 * Frame hooks, so the renderer never imports UI. UI modules subscribe from their init():
 *   onFrameEnd(fn(now))   once per frame, after everything else
 *   onFrameDrawn(fn(V))     after drawing, with the frame's level-of-detail state V
 */
const frameEnd = [],
  afterDraw = [];
export const onFrameEnd = fn => {
  frameEnd.push(fn);
};
export const onFrameDrawn = fn => {
  afterDraw.push(fn);
};

let raf = 0;
let lastT = 0;
export function requestRender() {
  if (!raf) raf = requestAnimationFrame(frame);
}
/** Is something flowing on the map (dots along a selection's contracts, a route, or an answer's trail)? */
function flowing() {
  if (store.dimT <= 0.02 || reduceMotion) return false;
  if (store.linkId >= 0 || store.httpImpact) return true;
  if (store.selectedId >= 0) return store.focusEdges.length > 0 && store.focusEdges.length <= 900;
  if (store.focusId === ROUTE_FOCUS) return routeActive();
  return store.focusId === ASK_FOCUS && store.askSet.length > 0 && store.askHops.length > 0;
}

function frame(now) {
  raf = 0;
  if (!store.G) return;
  const dt = lastT ? Math.min(0.05, (now - lastT) / 1000) : 0;
  lastT = now;
  let more = false;
  if (store.anim) more = stepAnim(now) || more;
  if (store.introP < 1) {
    store.introP = reduceMotion ? 1 : Math.min(1, (now - store.introT0) / 400);
    more = true;
  }
  const lerp = (v, g) => (Math.abs(g - v) > 0.004 ? ((more = true), v + (g - v) * Math.min(1, dt * 14)) : g);
  store.focusT = lerp(store.focusT, store.focusGoal);
  store.dimT = lerp(store.dimT, store.dimGoal);
  if (store.focusGoal === 0 && store.focusT === 0 && store.focusId >= 0) {
    store.focusId = -1;
    clearFocus();
  }
  if (flowing()) more = true;
  const t0 = performance.now();
  render(now);
  const ms = performance.now() - t0;
  store.cpuMs = store.cpuMs ? store.cpuMs * 0.85 + ms * 0.15 : ms;
  if (store.labelsAnimating) more = true;
  if (more) requestRender();
  else lastT = 0;
  for (const fn of frameEnd) fn(now);
}
// each level appears when its features are legible on screen (sizes in CSS pixels)
export const lod = k => {
  const g = store.G;
  const dAct = sstep(g.medD * k, 22, 45),
    sAct = sstep(g.medRF * k, 10, 20),
    lAct = sstep(k, 1.1, 1.8);
  return {
    k,
    dAct,
    sAct,
    lAct,
    aR: 1 - dAct,
    aD: dAct * (1 - sAct),
    aS: sAct * (1 - lAct),
    aL: lAct,
    svcA: sstep(g.medRS * k, 1.2, 3),
    leafA: sstep(g.medRF * k, 14, 26),
    aRL: 1 - sstep(g.medD * k, 60, 120),
    aDL: sstep(g.medD * k, 20, 36) * (1 - sstep(g.medRF * k, 45, 90)),
  };
};
export const scrR = i =>
  clamp(store.G.PR[i] * cam.k, i < store.G.S ? 1.4 : 0.6, i < store.G.S ? SVC_MAX_PX : LEAF_MAX_PX);
function drawEdges(L, alpha, stub = 0, fade = 0) {
  if (!L.n || alpha < 0.01) return;
  gl.uniform1f(P_EDGE.u.u_alpha, alpha);
  gl.uniform1f(P_EDGE.u.u_stub, store.G.N >= 5000 || L === LY.leafE ? stub : 0);
  gl.uniform1f(P_EDGE.u.u_fade, fade);
  gl.bindVertexArray(L.vao);
  gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, L.verts, L.n);
  store.drawn += L.n;
}
function drawNodes(L, alpha, minPx, maxPx) {
  if (!L.n || alpha < 0.01) return;
  gl.uniform1f(P_NODE.u.u_alpha, alpha);
  gl.uniform1f(P_NODE.u.u_minPx, minPx);
  gl.uniform1f(P_NODE.u.u_maxPx, maxPx);
  gl.bindVertexArray(L.vao);
  gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, L.n);
  store.drawn += L.n;
}
function drawFill(L, alpha) {
  if (!L.n || alpha < 0.01) return;
  gl.uniform1f(P_FILL.u.u_alpha, alpha);
  gl.bindVertexArray(L.vao);
  gl.drawArrays(gl.TRIANGLES, 0, L.n);
  store.drawn += L.n / 3;
}
function render(now) {
  const k = cam.k,
    I = easeOut(store.introP),
    V = lod(k),
    fd = 1 - 0.86 * store.dimT,
    hd = 1 - 0.5 * store.dimT;
  store.drawn = 0;
  gl.viewport(0, 0, glc.width, glc.height);
  gl.disable(gl.BLEND);
  gl.useProgram(P_BG.p);
  let gs = 40 * k;
  while (gs < 22) gs *= 2;
  while (gs > 44) gs /= 2;
  gl.uniform3f(P_BG.u.u_bg, theme.bg[0] / 255, theme.bg[1] / 255, theme.bg[2] / 255);
  gl.uniform4f(P_BG.u.u_grid, theme.grid[0] / 255, theme.grid[1] / 255, theme.grid[2] / 255, theme.grid[3]);
  gl.uniform2f(P_BG.u.u_size, store.W, store.H);
  gl.uniform1f(P_BG.u.u_dpr, store.dpr);
  gl.uniform3f(P_BG.u.u_g, gs, ((cam.x % gs) + gs) % gs, ((cam.y % gs) + gs) % gs);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  gl.enable(gl.BLEND);
  gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

  gl.useProgram(P_FILL.p);
  gl.uniform3f(P_FILL.u.u_cam, k, cam.x, cam.y);
  gl.uniform2f(P_FILL.u.u_size, store.W, store.H);
  drawFill(LY.repoFill, I * hd);
  drawFill(LY.domFill, I * hd * V.dAct);

  gl.useProgram(P_EDGE.p);
  gl.uniform3f(P_EDGE.u.u_cam, k, cam.x, cam.y);
  gl.uniform2f(P_EDGE.u.u_size, store.W, store.H);
  gl.uniform4f(P_EDGE.u.u_mask, 1, 1, 1, 1);
  drawEdges(LY.repoLine, I * hd * (1 - 0.35 * V.dAct));
  drawEdges(LY.domLine, I * hd * V.dAct * (1 - 0.4 * V.sAct));
  drawEdges(LY.repoB, I * fd * V.aR, 0, 70);
  drawEdges(LY.domB, I * fd * V.aD, 150, 40);
  drawEdges(LY.svcB, I * fd * V.aS, 90, 18);
  gl.uniform4f(
    P_EDGE.u.u_mask,
    stOn[0] && !store.issuesOnly ? 1 : 0,
    stOn[1] ? 1 : 0,
    stOn[2] ? 1 : 0,
    stOn[3] && !store.issuesOnly ? 1 : 0,
  );
  drawEdges(LY.leafE, I * fd * V.aL, 70);
  if (store.focusId >= 0) drawEdges(LY.focusE, I * store.focusT * (store.selectedId >= 0 ? 1 : 0.75));

  gl.useProgram(P_NODE.p);
  gl.uniform3f(P_NODE.u.u_cam, k, cam.x, cam.y);
  gl.uniform2f(P_NODE.u.u_size, store.W, store.H);
  gl.uniform1f(P_NODE.u.u_focusT, store.focusId >= 0 ? store.dimT : 0);
  gl.uniform1f(P_NODE.u.u_issues, store.issuesOnly ? 1 : 0);
  gl.uniform3f(P_NODE.u.u_halo, theme.halo[0] / 255, theme.halo[1] / 255, theme.halo[2] / 255);
  drawNodes(LY.leaves, I * V.leafA, 0.6, LEAF_MAX_PX);
  if (LY.route.n) {
    gl.useProgram(P_EDGE.p);
    gl.uniform4f(P_EDGE.u.u_mask, 1, 1, 1, 1);
    drawEdges(LY.routeCase, I);
    drawEdges(LY.route, I);
    gl.useProgram(P_NODE.p);
  }
  drawNodes(LY.svcs, I * Math.max(V.svcA, store.dimT * 0.999), 1.4, SVC_MAX_PX);
  gl.bindVertexArray(null);
  drawOverlay(now, V, I);
  drawMinimap();
  for (const fn of afterDraw) fn(V);
}
