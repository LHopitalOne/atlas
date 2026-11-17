/**
 * Welcome tour for the demo page (a build with --tour): a few steps that dim the page and light the parts that matter,
 * with a small card beside them. The viewer clicks a real link, switches maps and asks a sample question. It shows
 * once (remembered in localStorage when the browser allows it); the toolbar's Tour button plays it again.
 * The dim is one SVG path with a hole per lit part (even-odd fill): clicks in a hole reach the page, the rest is blocked.
 */
import { cam, store } from '../state.js';
import { TOUR } from '../config.js';
import { ASK, BLD, INSP, LINKS, ov } from '../dom.js';
import { esc } from '../util/format.js';
import { $ } from '../util/dom.js';
import { mapLabel, mapList } from '../model/maps.js';
import { isOutside, repoPairs } from '../model/http.js';
import { loadDataset } from '../app/dataset.js';
import { onFrameDrawn } from '../render/frame.js';
import { askOff, openAsk } from './ask.js';
import { autoOpenLinks, holdLinks, openLinksPanel } from './links.js';

let layer = null; // { root, shade, rings, card }, built the first time the tour opens
let steps = []; // the steps that apply to the map the tour started on
let at = -1; // the step on screen; -1 while the tour is closed
let startedOn = null; // the graph shown when the switch step began (it waits for another)
let switching = false; // Next on the switch step asked for the other map
let asked = false; // the sample question was sent
let shown = false; // the answer's diagram was scrolled into view
let settleUntil = 0; // follow the target every frame until then
let lastFocus = null;
let autoStarted = false;
let watcher = null; // ResizeObserver on the step's target
let drawn = ''; // what place() last drew, so a frame where nothing moved writes no styles
let movedAt = 0; // when the lit parts last moved
let linksShown = false; // the tour opened the links panel (else closing it opens the panel, as a map load would)
const SMOOTH = typeof CSS !== 'undefined' && CSS.supports('d', 'path("M0 0")'); // holes slide where `d` animates

const NUMBERS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const words = n => NUMBERS[n] || String(n);

// ---------------------------------------------------------------- what the steps say

/** Repositories on the map, without the stand-in for services outside them (where outside links end). */
function repoCount(g) {
  const H = g.http;
  if (!H) return g.R;
  const callers = new Set(H.links.map(l => l.call.repo));
  const outside = new Set(H.links.filter(l => isOutside(l) && !callers.has(l.route.repo)).map(l => l.route.repo));
  return g.R - outside.size;
}

const mapName = g => (mapList().length ? mapLabel(g.src) : 'this map');

function welcomeText(g) {
  const n = repoCount(g),
    by = /graphify/i.test((g.meta && (g.meta.source || g.meta.label)) || '') ? ' mapped by Graphify' : '';
  const lines = g.http
    ? 'Each line between colours is an HTTP call found in the code.'
    : 'Each colour is a repository; lines are calls between them.';
  return `This is ${mapName(g)}: ${words(n)} ${n === 1 ? 'repository' : 'repositories'}${by}. ${lines}`;
}

/** The map after the current one, for the switch step. */
function otherMap(g) {
  const maps = mapList(),
    i = maps.findIndex(m => m.key === g.src);
  return maps[(i + 1) % maps.length].key;
}

/** The sample question: set for the demo maps; elsewhere a route between the busiest pair of repositories. */
function question(g) {
  if (TOUR.ask[g.src]) return TOUR.ask[g.src];
  const H = g.http,
    pair = H && repoPairs(g, H).find(p => p.a !== p.b && !isOutside(H.links[H.groups[p.groups[0]].links[0]]));
  if (!pair) return TOUR.askPlain;
  return TOUR.askAny.replace('{from}', g.repoName[pair.a]).replace('{to}', g.repoName[pair.b]);
}

// ---------------------------------------------------------------- where the light goes

/** An element's box, or null when it is not on screen. */
function boxOf(el) {
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) return null;
  const cs = getComputedStyle(el);
  if (cs.visibility === 'hidden') return null; // not opacity: a panel fading in is already the target
  return { x: r.left, y: r.top, w: r.width, h: r.height };
}

function union(a, b) {
  if (!a || !b) return a || b;
  const x = Math.min(a.x, b.x),
    y = Math.min(a.y, b.y);
  return { x, y, w: Math.max(a.x + a.w, b.x + b.w) - x, h: Math.max(a.y + a.h, b.y + b.h) - y };
}

/** The link whose proof is open, on the map: its two ends and the arc between them. */
function linkBox() {
  const g = store.G,
    H = g && g.http,
    gr = H && store.linkId >= 0 && H.groups[store.linkId];
  if (!gr) return null;
  return screenBox([g.PX[gr.from], g.PX[gr.to]], [g.PY[gr.from], g.PY[gr.to]]);
}

/** Map points to a box on screen, padded for arcs that bulge past their ends. */
function screenBox(xs, ys) {
  const o = ov.getBoundingClientRect(),
    sx = v => v * cam.k + cam.x + o.left,
    sy = v => v * cam.k + cam.y + o.top;
  const x0 = sx(Math.min(...xs)),
    x1 = sx(Math.max(...xs)),
    y0 = sy(Math.min(...ys)),
    y1 = sy(Math.max(...ys));
  const w = Math.max(x1 - x0 + 2 * TOUR.linkPad, TOUR.minHole),
    h = Math.max(y1 - y0 + 2 * TOUR.linkPad, TOUR.minHole);
  return { x: (x0 + x1 - w) / 2, y: (y0 + y1 - h) / 2, w, h };
}

const switcher = () => boxOf($('#scale')) || boxOf($('#scaleSel'));

const between = gr => !!gr && !gr.within && gr.proof !== 'outside';
const httpOnly = (H, gr) => gr.links.every(i => (H.links[i].protocol || 'http') === 'http');
// a route or calling file under tests/ is real but a poor first example: production code reads better
const TESTS = /(^|\/)tests?(\/|$)/;
const production = (H, gr) =>
  gr.links.every(i => !TESTS.test(H.links[i].path || '') && !TESTS.test((H.links[i].call || {}).file || ''));

/**
 * The best-proven link in the panel between two repositories: an HTTP call in production code confirmed by SCIP, then
 * by syntax, then any HTTP call (tests included), then any link. The panel may list outside services or an inferred Kafka topic first.
 */
function firstLink() {
  const H = store.G.http;
  if (!H) return null; // a map without links (the tour may have switched to one)
  const all = [...LINKS.querySelectorAll('[data-link]')],
    rows = all.map(b => ({ b, gr: H.groups[+b.dataset.link] }));
  const tests = [
    gr => between(gr) && httpOnly(H, gr) && production(H, gr) && gr.proof === 'scip',
    gr => between(gr) && httpOnly(H, gr) && production(H, gr) && gr.proof === 'syntax',
    gr => between(gr) && httpOnly(H, gr) && gr.proof === 'scip',
    gr => between(gr) && httpOnly(H, gr) && gr.proof === 'syntax',
    gr => between(gr) && httpOnly(H, gr),
    between,
  ];
  for (const ok of tests) {
    const hit = rows.find(r => ok(r.gr));
    if (hit) return hit.b;
  }
  return all[0];
}

/** Open the links panel if the viewer closed it, and scroll its first link between repositories into view. */
function showLinks() {
  linksShown = true;
  if (!LINKS.classList.contains('on')) openLinksPanel();
  const b = firstLink(),
    box = b && b.closest('.scroll');
  if (box) box.scrollTop += b.getBoundingClientRect().top - box.getBoundingClientRect().top - box.clientHeight / 3;
  return b;
}

/** For keyboards: focus that link, so Enter opens it. */
function focusFirstLink() {
  const b = showLinks();
  if (b) b.focus({ preventScroll: true });
}

function switchMap() {
  if (switching) return;
  switching = true;
  loadDataset(otherMap(store.G));
  renderCard();
}

function sendQuestion() {
  asked = true;
  shown = false;
  openAsk(question(store.G));
  renderCard();
  focusCard();
  // the map may sit still while the answer streams in, so watch for the diagram here, not in tick()
  const wait = () => {
    if (at < 0 || steps[at].id !== 'ask' || shown) return;
    showDiagram();
    if (!shown) requestAnimationFrame(wait);
  };
  requestAnimationFrame(wait);
}

const STEPS = [
  {
    id: 'welcome',
    soft: true, // a light dim and no lit box: the card introduces the whole map
    title: () => 'Welcome to Atlas',
    text: welcomeText,
    target: () => null,
    free: true, // lights nothing on purpose: the card shows at once, in the middle
    next: { label: () => 'Start the tour', act: () => go(at + 1) },
  },
  {
    id: 'link',
    applies: g => !!g.http,
    title: () => 'Click a link',
    text: () => 'Each row is a request one repository sends to another. Click one to see the code behind it.',
    wait: () => 'Waiting for you to click a link…',
    enter: showLinks,
    target: () => boxOf(LINKS),
    el: () => LINKS,
    next: { label: () => 'Choose a link', act: focusFirstLink },
  },
  {
    id: 'proof',
    applies: g => !!g.http,
    title: () => 'The proof',
    text: () =>
      'Two lines of code: the line that sends the request, and the route that serves it. Each links to GitHub at the commit that was mapped.',
    target: () => union(boxOf(INSP), boxOf($('#code'))),
    extra: linkBox, // the link itself, lit on the map too
    el: () => INSP,
  },
  {
    id: 'switch',
    applies: () => mapList().length > 1,
    title: g => `Switch to ${mapLabel(otherMap(g))}`,
    text: () => 'Same idea, different company: its repositories, and the HTTP calls between them.',
    wait: () => (switching ? 'Loading the map…' : ''),
    enter: () => {
      startedOn = store.G;
      switching = false;
    },
    target: switcher,
    next: { label: g => `Show ${mapLabel(otherMap(g))}`, act: switchMap },
  },
  {
    id: 'ask',
    applies: () => !askOff(),
    title: () => 'Ask Atlas',
    text: () =>
      asked
        ? 'The answer streams in, then draws the route it found, file by file. After the tour, click a box to find it on the map.'
        : 'Ask about the code in plain words. Try this one: the answer draws the route as a diagram.',
    enter: () => {
      asked = false;
      openAsk();
      // openAsk focuses the text box; on a phone that would open the keyboard just to close it again
      ASK.querySelector('textarea')?.blur();
    },
    target: () => boxOf(ASK),
    el: () => ASK,
  },
];

// ---------------------------------------------------------------- drawing

function build() {
  const root = document.createElement('div');
  root.className = 'tour';
  root.hidden = true;
  root.innerHTML = `<svg class="tour-shade" aria-hidden="true"><path fill-rule="evenodd"></path><g></g></svg>
    <div class="tour-card card" role="dialog" aria-modal="false" aria-labelledby="tourTitle" aria-describedby="tourText" tabindex="-1"></div>`;
  document.body.appendChild(root);
  layer = {
    root,
    shade: root.querySelector('.tour-shade path'),
    rings: root.querySelector('.tour-shade g'),
    card: root.querySelector('.tour-card'),
  };
  layer.card.addEventListener('click', onCardClick);
  watcher = new ResizeObserver(() => place());
}

function renderCard() {
  const st = steps[at],
    g = store.G,
    last = at === steps.length - 1;
  const wait = st.wait && st.wait(g);
  const q =
    st.id === 'ask' && !asked ? `<button class="chip-q tour-q" data-tour="ask">${esc(question(g))}</button>` : '';
  const nextLabel = st.next ? st.next.label(g) : last ? 'Finish' : 'Next';
  const busy = st.id === 'switch' && switching;
  drawn = '';
  layer.card.innerHTML = `<div class="tour-top"><span class="tour-n">${at + 1} of ${steps.length}</span><button class="btn btn-ghost btn-sm" data-tour="skip">Skip tour</button></div>
    <h2 id="tourTitle">${esc(st.title(g))}</h2><p id="tourText">${esc(st.text(g))}</p>${wait ? `<div class="tour-wait" role="status">${esc(wait)}</div>` : ''}${q}
    <div class="tour-nav">${at > 0 ? '<button class="btn btn-ghost btn-sm" data-tour="back">Back</button>' : ''}<button class="btn ${q ? 'btn-outline' : 'btn-primary'} btn-sm" data-tour="next"${busy ? ' aria-disabled="true"' : ''}>${esc(nextLabel)}</button></div>`;
}

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

/** Keep the lit box inside the window, with a margin around the target. */
function fit(r, W, H) {
  if (!r) return null;
  const x = clamp(r.x - TOUR.pad, 0, W),
    y = clamp(r.y - TOUR.pad, 0, H),
    x1 = clamp(r.x + r.w + TOUR.pad, 0, W),
    y1 = clamp(r.y + r.h + TOUR.pad, 0, H);
  return x1 - x < 2 || y1 - y < 2 ? null : { x, y, w: x1 - x, h: y1 - y };
}

/** A rounded rectangle as a path, for one hole in the dim. */
function roundRect({ x, y, w, h }) {
  const r = Math.min(TOUR.radius, w / 2, h / 2);
  return `M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
}

const meets = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/** The part of `b` beside `a`, on whichever side leaves more of it (a link running under the proof panel is lit up
 * to the panel's edge, not merged with it); null when too little is left to see. */
function beside(b, a) {
  if (!b || !a || !meets(a, b)) return b;
  const left = a.x - TOUR.gap - b.x,
    right = b.x + b.w - (a.x + a.w + TOUR.gap);
  const out = left >= right ? { ...b, w: left } : { ...b, x: a.x + a.w + TOUR.gap, w: right };
  return out.w >= TOUR.minHole / 2 ? out : null;
}

/** Lit boxes that overlap become one: with an even-odd fill, an overlap would be dimmed again. */
function merge(boxes) {
  const out = [];
  for (let b of boxes) {
    for (let i = out.length - 1; i >= 0; i--)
      if (meets(out[i], b)) {
        b = union(out[i], b);
        out.splice(i, 1);
      }
    out.push(b);
  }
  return out;
}

/** The dim over the whole window with a hole for each lit box, and a thin ring around each hole. */
function drawHoles(boxes, W, H) {
  const d = `M0 0H${W}V${H}H0Z` + boxes.map(roundRect).join('');
  if (SMOOTH) layer.shade.style.d = `path("${d}")`;
  else layer.shade.setAttribute('d', d);
  const r = b => Math.min(TOUR.radius, b.w / 2, b.h / 2);
  layer.rings.innerHTML = boxes
    .map(b => `<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="${r(b)}"></rect>`)
    .join('');
}

/** Beside the lit box: right, left, below or above, whichever fits first without covering a lit part; else at the
 * bottom. With nothing lit, in the middle. */
function cardSpot(r, cw, ch, W, H, lit) {
  const m = TOUR.edge,
    gap = TOUR.gap;
  if (!r) return { x: (W - cw) / 2, y: (H - ch) / 2 };
  const clear = s => !lit.some(b => meets(b, { x: s.x, y: s.y, w: cw, h: ch }));
  const ys = clamp(r.y, m, H - ch - m),
    xs = clamp(r.x, m, W - cw - m);
  const spots = [
    { x: r.x + r.w + gap, y: ys, ok: r.x + r.w + gap + cw <= W - m },
    { x: r.x - gap - cw, y: ys, ok: r.x - gap - cw >= m },
    { x: xs, y: r.y + r.h + gap, ok: r.y + r.h + gap + ch <= H - m },
    { x: xs, y: r.y - gap - ch, ok: r.y - gap - ch >= m },
    // with more than one lit part, a corner over the dim beats covering one of them
    { x: m, y: TOUR.top, ok: true },
    { x: m, y: H - ch - m, ok: true },
    { x: W - cw - m, y: TOUR.top, ok: true },
    { x: W - cw - m, y: H - ch - m, ok: true },
  ];
  return spots.find(s => s.ok && clear(s)) || spots.find(s => s.ok);
}

function placeCard(r, W, H, lit) {
  const card = layer.card,
    sheet = matchMedia(TOUR.phone).matches;
  card.classList.toggle('sheet', sheet);
  if (sheet) {
    // a sheet sits at the bottom, unless the lit part is in the lower half
    card.classList.toggle('top', !!r && r.y + r.h / 2 > H / 2);
    card.style.translate = '';
    return;
  }
  card.classList.remove('top');
  const s = cardSpot(r, card.offsetWidth, card.offsetHeight, W, H, lit);
  card.style.translate = `${Math.round(s.x)}px ${Math.round(s.y)}px`;
}

/** Light the current step's target and put the card beside it. */
function place() {
  if (at < 0) return;
  const st = steps[at],
    W = innerWidth,
    H = innerHeight,
    r = fit(st.target(), W, H),
    more = st.extra ? beside(fit(st.extra(), W, H), r) : null,
    lit = merge([r, more].filter(Boolean));
  const key = [at, W, H, layer.card.offsetHeight, ...lit.flatMap(b => [b.x, b.y, b.w, b.h].map(Math.round))].join();
  // while the step's panel slides in or the map flies, keep the card hidden rather than show it somewhere and move it:
  // it appears once the lit parts hold still for a frame (or the settling time is up)
  const now = performance.now();
  if (key !== drawn) movedAt = now;
  // place() can run twice in one frame (the settle loop and the map's redraw): still means still across frames
  const still = now - movedAt >= TOUR.stillMs,
    pending = !st.free && (!r || !still) && now < settleUntil;
  if (key === drawn && pending === layer.card.classList.contains('pending')) return;
  drawn = key;
  layer.root.classList.toggle('soft', !!st.soft);
  drawHoles(lit, W, H);
  placeCard(r || lit[0] || null, W, H, lit);
  const appears = layer.card.classList.contains('pending') && !pending;
  layer.card.classList.toggle('pending', pending);
  if (appears) {
    enter(); // shown for the first time: play its entrance
    layer.card.focus({ preventScroll: true }); // a hidden card could not take focus when the step began
  }
}

/** Every frame for a moment after a change, so the light follows panels as they slide in. */
function settle() {
  settleUntil = performance.now() + TOUR.settleMs;
  layer.root.classList.add('moving');
  const loop = () => {
    tick();
    if (at >= 0 && performance.now() < settleUntil) requestAnimationFrame(loop);
    else {
      layer.root.classList.remove('moving');
      place(); // a target that never showed: the card appears anyway, where place() puts it
    }
  };
  requestAnimationFrame(loop);
}

/** Once the sample answer draws its diagram, scroll the Ask panel to it (on a phone it starts below the fold). */
function showDiagram() {
  const pic = ASK.querySelector('.gv'),
    box = pic && pic.closest('.ask-thread');
  if (!box) return;
  shown = true;
  const p = pic.getBoundingClientRect(),
    b = box.getBoundingClientRect();
  if (p.bottom > b.bottom) box.scrollTop += Math.min(p.top - b.top - TOUR.gap, p.bottom - b.bottom + TOUR.gap);
}

/** Follow the target; on the switch step, move on once the other map is showing. */
function tick() {
  if (at < 0) return;
  const st = steps[at];
  if (st.id === 'switch' && !BLD.classList.contains('on')) {
    if (store.G !== startedOn) return go(at + 1);
    if (switching) {
      switching = false; // the other map failed to load (dataset.js said so in a toast): let Next try again
      renderCard();
    }
  }
  // the viewer closed the links panel while it is the target: open it again
  if (st.id === 'link' && !store.linksOpen && store.G.http) showLinks();
  place();
}

function focusCard() {
  requestAnimationFrame(() => requestAnimationFrame(() => at >= 0 && layer.card.focus({ preventScroll: true })));
}

// ---------------------------------------------------------------- steps and controls

function go(k) {
  if (k >= steps.length) return close();
  const back = k < at;
  at = Math.max(0, k);
  const st = steps[at];
  // going back to the proof with no link open: back to choosing one
  if (back && st.id === 'proof' && store.linkId < 0) return go(at - 1);
  if (st.enter) st.enter();
  renderCard();
  settleUntil = performance.now() + TOUR.settleMs; // place() hides the card until the target is on screen
  enter();
  watcher.disconnect();
  const el = st.el && st.el();
  if (el) watcher.observe(el);
  place();
  settle();
  focusCard();
}

/** Play the card's entrance (a short fade and rise in place). */
function enter() {
  layer.card.classList.remove('enter');
  void layer.card.offsetWidth; // restart the animation
  layer.card.classList.add('enter');
}

function onCardClick(e) {
  const b = e.target.closest('[data-tour]');
  if (!b || at < 0 || b.getAttribute('aria-disabled') === 'true') return;
  const st = steps[at],
    act = b.dataset.tour;
  if (act === 'skip') return close();
  if (act === 'back') return go(at - 1);
  if (act === 'ask') return sendQuestion();
  if (st.next) return st.next.act();
  go(at + 1);
}

/** The links step waits for a real link: the links panel opens its proof, then the tour moves on. */
function onLinksClick(e) {
  if (at >= 0 && steps[at].id === 'link' && e.target.closest('[data-link]')) go(at + 1);
}

function onKey(e) {
  if (at < 0 || e.key !== 'Escape') return;
  e.preventDefault();
  e.stopPropagation(); // the page's own Escape would close a panel too
  close();
}

const onResize = () => place();

function remember() {
  try {
    localStorage.setItem(TOUR.storeKey, '1');
  } catch (_) {
    // storage blocked: the tour shows again next time
  }
}

function seen() {
  try {
    return localStorage.getItem(TOUR.storeKey) === '1';
  } catch (_) {
    return false;
  }
}

/** Open the tour at its first step (the Tour button, or the first visit). */
export function startTour() {
  if (!layer || at >= 0 || !store.G) return;
  steps = STEPS.filter(s => !s.applies || s.applies(store.G));
  lastFocus = document.activeElement;
  linksShown = false;
  holdLinks(true); // the links panel waits for the step about it
  layer.root.hidden = false;
  addEventListener('keydown', onKey, true);
  addEventListener('resize', onResize);
  // panels slide and fade in with CSS: follow them to where they stop
  document.addEventListener('transitionend', onResize, true);
  document.addEventListener('animationend', onResize, true);
  go(0);
  requestAnimationFrame(() => layer.root.classList.add('on'));
}

/** Close the tour (Skip, Escape or Finish); it is not shown again on its own. */
export function closeTour() {
  if (at >= 0) close();
}

function close() {
  at = -1;
  remember();
  holdLinks(false);
  if (!linksShown) autoOpenLinks(); // closed before the links step: show the map as it would have opened
  watcher.disconnect();
  removeEventListener('keydown', onKey, true);
  removeEventListener('resize', onResize);
  document.removeEventListener('transitionend', onResize, true);
  document.removeEventListener('animationend', onResize, true);
  layer.root.classList.remove('on', 'moving');
  setTimeout(() => at < 0 && (layer.root.hidden = true), TOUR.fadeMs);
  const back = lastFocus && document.contains(lastFocus) && lastFocus.offsetParent ? lastFocus : ov;
  back.focus({ preventScroll: true });
}

/** Wire the tour on pages built with --tour. Called once from main.js. */
export function init() {
  if (!document.getElementById('tourOn')) return;
  build();
  const btn = $('#tourBtn');
  btn.hidden = false;
  btn.addEventListener('click', startTour);
  LINKS.addEventListener('click', onLinksClick);
  if (!seen()) holdLinks(true); // the tour starts on its own: keep the links panel for its step
  onFrameDrawn(() => {
    if (at >= 0) return tick();
    // the first visit: start once the first map is on screen and its intro flight is done
    if (autoStarted || !store.G || BLD.classList.contains('on')) return;
    autoStarted = true;
    if (!seen()) setTimeout(startTour, TOUR.startMs);
  });
}
