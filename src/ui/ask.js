/**
 * Ask Atlas: a conversation about the codebase in the left panel. Questions come from the search bar ("Ask Atlas: …")
 * or the composer. Answers cite map items as numbered chips: hover lights the item on the map, click selects it, and
 * "Show on map" dims everything else. Claude answers when the page may ask it; otherwise the offline answerer does,
 * and the panel says which.
 */
import { store, route } from '../state.js';
import { ASK, ov } from '../dom.js';
import { esc } from '../util/format.js';
import { renderAnswer } from '../ask/format.js';
import { refName, resolve, search, toolSet } from '../ask/tools.js';
import { answerLocally } from '../ask/local.js';
import { askClaude, claudeAvailable, disableClaude } from '../ask/claude.js';
import { sourceLines } from './code-view.js';
import { select } from '../app/selection.js';
import { setHover, updateFocus } from '../app/focus.js';
import { fitNodes, flyTo, flyToTerr } from '../app/camera.js';
import { requestRender } from '../render/frame.js';
import { announce } from './feedback.js';
import { closeDirections } from './directions.js';
import { renderAttn, syncLegend } from './attention.js';
import { dotHTML, ICON_X } from './fragments.js';
import { DEMO_QUESTION, scriptFor } from '../ask/demo.js';
import { ASK_ENGINE, ASK_PLAYBACK } from '../config.js';
import { reduceMotion } from '../util/dom.js';
import { ensureReverse } from '../graph/route-search.js';

/** Conversation: { q, text, steps, status: 'thinking'|'streaming'|'done'|'error', mode: 'claude'|'local', note } */
let thread = [];
let busy = null; // AbortController of the running question
let mode = ASK_ENGINE === 'demo' ? 'demo' : 'local';
let showing = -1; // index of the answer whose items are on the map
let mention = null; // { start, items, act }

const ICON_SEND =
  '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true"><path d="M7 12V2M2.5 6.5 7 2l4.5 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const ICON_STOP =
  '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="8" height="8" rx="1.5" fill="currentColor"/></svg>';
const ICON_NEW =
  '<svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';

export const askOpen = () => ASK.classList.contains('on');

const SELF_SUGGESTIONS = [
  DEMO_QUESTION,
  'What breaks if I change routeSearch?',
  'Who uses store?',
  'How does placeLabels reach requestRender?',
];

/** Suggestions for an empty conversation, chosen so each one has a real answer on the current map. */
function suggestions() {
  const g = store.G,
    sel = store.selectedId >= 0 ? g.name(store.selectedId) : null;
  if (g.src === 'self')
    return sel ? [SELF_SUGGESTIONS[0], `What does ${sel} do?`, ...SELF_SUGGESTIONS.slice(1, 3)] : SELF_SUGGESTIONS;
  // demo maps: the most-used service, and a caller two steps away from it, so the route question has an answer
  ensureReverse(g); // who-calls-whom is built on first use
  let hub = 0;
  for (let s = 1; s < g.S; s++) if (g.QO[s + 1] - g.QO[s] > g.QO[hub + 1] - g.QO[hub]) hub = s;
  const callerOf = s => (g.QO[s + 1] > g.QO[s] ? g.dr.a[g.QI[g.QO[s]]] : -1);
  const c1 = callerOf(hub),
    c2 = c1 >= 0 ? callerOf(c1) : -1,
    from = c2 >= 0 && c2 !== hub ? c2 : c1;
  return [
    sel ? `What does ${sel} do?` : 'What is this codebase?',
    `What breaks if I change ${g.svcName[hub]}?`,
    `Who uses ${g.svcName[hub]}?`,
    ...(from >= 0 ? [`How does ${g.svcName[from]} reach ${g.svcName[hub]}?`] : []),
  ];
}

/** Open the panel, optionally asking a question right away. */
export function openAsk(question) {
  if (route.from || route.to || route.picking) closeDirections();
  if (store.attnOpen) {
    store.attnOpen = false;
    renderAttn();
  }
  const first = !askOpen();
  ASK.classList.add('on');
  syncLegend();
  if (first) render();
  if (ASK_ENGINE === 'claude')
    claudeAvailable().then(fn => {
      const m = fn ? 'claude' : 'local';
      if (m !== mode) {
        mode = m;
        renderHead();
      }
    });
  if (question && question.trim()) ask(question.trim());
  else ASK.querySelector('textarea').focus();
}

/** Close the panel (the conversation is kept until "New conversation"). */
export function closeAsk() {
  if (!askOpen()) return;
  if (busy) busy.abort();
  // a hidden text box would keep focus and swallow shortcuts: hand focus back to the map
  const hadFocus = ASK.contains(document.activeElement);
  ASK.classList.remove('on');
  clearShowing();
  syncLegend();
  if (hadFocus) ov.focus({ preventScroll: true });
}

/** Light up an answer's items on the map (everything else dims) and bring them into view. */
function showOnMap(i, quiet) {
  const { refs } = renderAnswer(thread[i].text, valid, nameOf);
  if (refs.length < 2 && quiet) return;
  clearShowing();
  showing = i;
  store.askSet = refs;
  store.focusId = -1;
  updateFocus();
  const b = ASK.querySelector(`[data-show="${i}"]`);
  if (b) {
    b.setAttribute('aria-pressed', 'true');
    b.textContent = 'Hide on map';
  }
  if (store.selectedId < 0)
    flyTo(
      fitNodes(
        store.focusList.filter(n => n < store.G.S),
        2,
      ),
    );
  if (!quiet) announce(`Showing ${refs.length} items from the answer on the map.`);
}

function clearShowing() {
  if (showing < 0) return;
  showing = -1;
  store.askSet = [];
  store.focusId = -1;
  updateFocus();
  ASK.querySelectorAll('[data-show]').forEach(b => {
    b.setAttribute('aria-pressed', 'false');
    b.textContent = 'Show on map';
  });
}

// ---------------------------------------------------------------- asking

const nameOf = ref => refName(store.G, ref);
const valid = ref => !!resolve(store.G, ref);
const contextRef = () => (store.selectedId >= 0 ? 'n' + store.selectedId : null);

/** Replace @mentions by names and collect their refs. */
function readMentions(q) {
  const refs = [];
  const text = q.replace(/@([\w$./-]+)/g, (m, name) => {
    const e = resolve(store.G, name);
    if (e) refs.push(e.t + e.id);
    return name;
  });
  return { text, refs };
}

// ---------------------------------------------------------------- simulated playback

/** Wait, unless motion is reduced; rejects as cancelled when Stop is pressed. */
const wait = (ms, signal) =>
  new Promise((done, fail) => {
    if (signal.aborted) return fail({ code: 'cancelled' });
    const t = setTimeout(done, reduceMotion ? 0 : ms);
    signal.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        fail({ code: 'cancelled' });
      },
      { once: true },
    );
  });

/** Ring an item on the map while the answer talks about it. */
const ring = ref => {
  const e = ref && resolve(store.G, ref);
  if (e) setHover({ t: e.t, id: e.id }, true);
};

/** Words, spaces and citations as separate tokens, so a citation never streams in half-written. */
const tokens = text => text.split(/(\[\[[ndr]\d+\]\]|\s+)/).filter(Boolean);

/** Play a script: think, show each step (ringing its item), then stream the text in. */
async function play(turn, i, script, signal) {
  await wait(ASK_PLAYBACK.think, signal);
  for (const st of script.steps) {
    turn.steps.push(st.label);
    turn.stepAt.push(performance.now());
    if (st.ref) ring(st.ref);
    renderTurn(i);
    await wait(st.ms || 440, signal);
  }
  turn.status = 'streaming';
  const all = tokens(script.text);
  for (let k = 0; k < all.length; ) {
    k = reduceMotion ? all.length : Math.min(all.length, k + ASK_PLAYBACK.tokensPerTick);
    turn.text = all.slice(0, k).join('');
    for (const m of turn.text.matchAll(/\[\[([ndr]\d+)\]\]/g))
      if (!turn.appear[m[1]]) {
        turn.appear[m[1]] = performance.now();
        ring(m[1]);
      }
    renderTurn(i);
    if (k < all.length) await wait(ASK_PLAYBACK.tick, signal);
  }
  turn.text = script.text;
}

/** Ask Claude with the map's tools, streaming into the turn. */
async function answerWithClaude(turn, q, refs, sel, ctl) {
  const g = store.G;
  const onStep = label => {
    turn.steps.push(label);
    turn.stepAt.push(performance.now());
    renderTurn(thread.length - 1);
  };
  const ctx = [
    `Map: ${g.src === 'self' ? 'Atlas’s own source code' : `a demo map of ${g.N} nodes`} (${g.R} repositories, ${g.S} services, ${g.L} endpoints).`,
    sel
      ? `Selected: ${g.name(+sel.slice(1))} (ref ${sel}). "This" or "it" means the selection.`
      : 'Nothing is selected.',
    refs.length ? `Mentioned: ${refs.map(r => `${nameOf(r)} (ref ${r})`).join(', ')}.` : '',
  ]
    .filter(Boolean)
    .join('\n');
  const history = thread
    .slice(0, -1)
    .filter(t => t.status === 'done')
    .slice(-4)
    .flatMap(t => [
      { role: 'user', content: t.q },
      { role: 'assistant', content: t.text },
    ]);
  turn.text = await askClaude({
    question: q,
    history,
    context: ctx,
    nameOf,
    signal: ctl.signal,
    onStep,
    tools: toolSet(g, { readSource: id => sourceLines(id) }),
    onText: t => {
      turn.text = t;
      turn.status = 'streaming';
      renderTurn(thread.length - 1);
    },
  });
}

/** A stopped or failed answer: keep what can stay; fall back to the index when Claude isn't available. */
function onFailure(turn, e, q, refs, sel) {
  const g = store.G;
  turn.text = (e && e.text) || turn.text;
  if (e && e.code === 'cancelled') {
    setHover(null);
    turn.status = 'done';
    turn.doneAt = performance.now();
    turn.note = 'Stopped.';
  } else if (
    e &&
    [
      'not_granted',
      'sampling_disabled',
      'capability_disabled',
      'capability_removed',
      'not_declared',
      'unavailable',
      'tools_unavailable',
    ].includes(e.code)
  ) {
    // Claude isn't allowed here: answer from the index instead, and say so
    disableClaude();
    mode = 'local';
    renderHead();
    turn.mode = 'local';
    turn.steps = [];
    turn.note = 'Claude isn’t available for this page, so this answer comes from the index only.';
    turn.text = answerLocally(g, q, { context: refs[0] || sel, onStep: l => turn.steps.push(l) });
    turn.status = 'done';
  } else {
    turn.status = 'error';
    turn.note =
      e && e.code === 'rate_limited'
        ? 'Too many questions at once. Try again in a moment.'
        : 'Something went wrong while answering. Try again.';
  }
}

async function ask(raw) {
  if (busy) busy.abort();
  const g = store.G,
    { text: q, refs } = readMentions(raw);
  const turn = {
    q: raw,
    text: '',
    steps: [],
    stepAt: [],
    appear: {},
    born: performance.now(),
    doneAt: 0,
    status: 'thinking',
    mode,
    note: '',
  };
  thread.push(turn);
  clearShowing();
  renderThread(true);
  const ctl = (busy = new AbortController());
  renderComposer(); // Send becomes Stop while answering
  const sel = contextRef();
  try {
    if (ASK_ENGINE === 'claude' && mode === 'claude') {
      await answerWithClaude(turn, q, refs, sel, ctl);
    } else {
      const script = scriptFor(g, q, { context: refs[0] || sel });
      if (script.note) turn.note = script.note;
      await play(turn, thread.length - 1, script, ctl.signal);
    }
    turn.status = 'done';
    turn.doneAt = performance.now();
    announce('Answer ready.');
    setHover(null);
    if (!turn.note) showOnMap(thread.length - 1, true);
  } catch (e) {
    onFailure(turn, e, q, refs, sel);
  } finally {
    if (busy === ctl) busy = null;
    renderTurn(thread.length - 1);
    renderComposer();
  }
}

// ---------------------------------------------------------------- rendering

function renderHead() {
  const h = ASK.querySelector('.ask-mode');
  if (!h) return;
  h.textContent = mode === 'claude' ? 'Claude' : mode === 'demo' ? 'Demo' : 'Offline';
  h.title =
    mode === 'demo'
      ? 'Simulated answers for this prototype: a scripted walkthrough for rendering questions, answers from the index otherwise. The product answers with Claude.'
      : mode === 'claude'
        ? 'Answers by Claude, using Atlas’s index. Uses your Claude account.'
        : 'Answers come from the index, without AI. Works for common questions.';
}

function render() {
  ASK.innerHTML = `<div class="ph"><div><h2>Ask Atlas <span class="badge badge-outline ask-mode"></span></h2></div>
    <div class="ph-actions"><button class="btn btn-ghost btn-icon" data-new aria-label="New conversation" title="New conversation">${ICON_NEW}</button>
    <button class="btn btn-ghost btn-icon" data-close-ask aria-label="Close Ask Atlas">${ICON_X}</button></div></div>
    <div class="lp-body scroll ask-thread" aria-live="polite"></div>
    <div class="composer"><div class="ctx"></div><div class="mentions" role="listbox" hidden></div>
      <div class="cbox"><textarea rows="1" placeholder="Ask about the code… (@ to mention)" aria-label="Ask Atlas a question"></textarea>
      <button class="send" data-send aria-label="Send">${ICON_SEND}</button></div>
      <div class="chint">Enter to send · Shift+Enter for a new line</div></div>`;
  renderHead();
  renderThread();
  renderComposer();
}

function renderThread(scroll) {
  const box = ASK.querySelector('.ask-thread');
  if (!box) return;
  if (!thread.length) {
    box.innerHTML = `<div class="ask-empty"><p>Ask anything about this codebase: what something does, what breaks if it changes, how two things connect.</p>
      <div class="sugg">${suggestions()
        .map(s => `<button class="chip-q" data-q="${esc(s)}">${esc(s)}</button>`)
        .join('')}</div></div>`;
    return;
  }
  box.innerHTML = thread.map((_, i) => `<div class="turn" data-turn="${i}"></div>`).join('');
  thread.forEach((_, i) => renderTurn(i));
  if (scroll) box.scrollTop = box.scrollHeight;
}

function stepsHTML(t) {
  if (!t.steps.length && t.status === 'thinking')
    return `<div class="steps running" data-at="${t.born}"><span class="shimmer">Thinking…</span></div>`;
  if (!t.steps.length) return '';
  const live = t.status === 'thinking';
  if (live)
    return `<ol class="steps running" data-at="${t.stepAt[0]}">${t.steps
      .map(
        (s, k) =>
          `<li data-at="${t.stepAt[k]}" class="${k === t.steps.length - 1 ? 'now' : 'did'}"><span class="${k === t.steps.length - 1 ? 'shimmer' : ''}">${esc(s)}</span></li>`,
      )
      .join('')}</ol>`;
  const readCode = t.steps.some(s => s.startsWith('Read the code'));
  const label = `Looked at ${t.steps.length} thing${t.steps.length === 1 ? '' : 's'}${readCode ? ' · read code live' : ' · from the index'}`;
  return `<details class="steps"><summary>${label}</summary><ol>${t.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol></details>`;
}

/** The blinking caret goes at the end of the text, inside the last paragraph or list item. */
const withCaret = html => {
  const caret = '<span class="caret" aria-hidden="true"></span>';
  const m = html.match(/<\/(p|li)>(?![\s\S]*<\/(p|li)>)/);
  return m ? html.slice(0, m.index) + caret + html.slice(m.index) : html + caret;
};

/** Entrance animations resume where they were: each element carries the time it first appeared. */
function resumeAnimations(el, t) {
  const now = performance.now();
  el.querySelectorAll('[data-at]').forEach(x => {
    x.style.animationDelay = `${Math.min(0, +x.dataset.at - now)}ms`;
  });
  el.querySelectorAll('.cite').forEach(x => {
    const at = t.appear[x.dataset.ref];
    x.style.animationDelay = `${at ? Math.min(0, at - now) : -1000}ms`;
  });
}

function renderTurn(i) {
  const el = ASK.querySelector(`.turn[data-turn="${i}"]`);
  if (!el) return renderThread(true);
  const t = thread[i],
    streaming = t.status === 'thinking' || t.status === 'streaming';
  const r = renderAnswer(t.text || '', valid, nameOf, streaming);
  const sources = r.refs.length
    ? `<div class="sources"><div class="src-h">Sources</div>${r.refs
        .map((ref, n) => {
          const e = resolve(store.G, ref),
            dot = e.t === 'n' ? dotHTML(e.id) : '<span class="g tr" aria-hidden="true"></span>';
          const where =
            e.t === 'n'
              ? `${store.G.repoName[store.G.domRepo[store.G.svcDom[store.G.own(e.id)]]]} · ${store.G.domName[store.G.svcDom[store.G.own(e.id)]]}`
              : e.t === 'd'
                ? 'Domain'
                : 'Repository';
          return `<button class="src" data-ref="${ref}" data-at="${t.appear[ref] || t.born}"><span class="n">${n + 1}</span>${dot}<span class="sn${e.t === 'n' && e.id >= store.G.S ? ' mono' : ''}">${esc(nameOf(ref))}</span><span class="sw">${esc(where)}</span></button>`;
        })
        .join('')}</div>`
    : '';
  const done = t.status === 'done' || t.status === 'error';
  const actions =
    done && r.refs.length
      ? `<div class="ans-actions" data-at="${t.doneAt}"><button class="btn btn-outline btn-sm" data-show="${i}" aria-pressed="${showing === i}">${showing === i ? 'Hide on map' : 'Show on map'}</button></div>`
      : '';
  const follow =
    done && r.followups.length && i === thread.length - 1
      ? `<div class="sugg follow" data-at="${t.doneAt}">${r.followups.map(s => `<button class="chip-q" data-q="${esc(s)}">${esc(s)}</button>`).join('')}</div>`
      : '';
  el.innerHTML = `<div class="uq" data-at="${t.born}">${esc(t.q)}</div><div>${stepsHTML(t)}${t.note ? `<div class="ans-note">${esc(t.note)}</div>` : ''}
    <div class="ans-text">${t.status === 'streaming' ? withCaret(r.html) : r.html}</div>${sources}${actions}${follow}
    ${done && !t.note ? (t.mode === 'demo' ? '<div class="ans-meta">Simulated answer for this prototype.</div>' : t.mode === 'local' ? '<div class="ans-meta">Answered from the index, without AI.</div>' : '') : ''}</div>`;
  resumeAnimations(el, t);
  if (t.status !== 'done') {
    const box = ASK.querySelector('.ask-thread');
    box.scrollTop = box.scrollHeight;
  }
}

function renderComposer() {
  const btn = ASK.querySelector('[data-send]'),
    ta = ASK.querySelector('textarea'),
    ctx = ASK.querySelector('.ctx');
  if (!btn) return;
  btn.innerHTML = busy ? ICON_STOP : ICON_SEND;
  btn.setAttribute('aria-label', busy ? 'Stop' : 'Send');
  btn.classList.toggle('stop', !!busy);
  btn.disabled = !busy && !ta.value.trim();
  const sel = store.selectedId;
  ctx.innerHTML =
    sel >= 0
      ? `<span class="ctx-chip" title="“This” refers to the selected item">About ${dotHTML(sel)}<span class="${sel >= store.G.S ? 'mono' : ''}">${esc(store.G.name(sel))}</span></span>`
      : '';
}

/** Keep the "About …" chip in step with the selection. */
export function syncAskContext() {
  if (askOpen()) renderComposer();
}

// ---------------------------------------------------------------- composer: auto-grow, Enter to send, @ mentions

function grow(ta) {
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 132) + 'px';
}

function updateMentions(ta) {
  const before = ta.value.slice(0, ta.selectionStart),
    m = before.match(/@([\w$./-]*)$/),
    box = ASK.querySelector('.mentions');
  if (!m || !store.G) {
    mention = null;
    box.hidden = true;
    return;
  }
  const items = (m[1] ? search(store.G, { query: m[1], limit: 6 }) : []).filter(
    x => x.kind !== 'repository' || m[1].length > 1,
  );
  if (!items.length) {
    mention = null;
    box.hidden = true;
    return;
  }
  mention = { start: before.length - m[0].length, end: before.length, items, act: 0 };
  drawMentions();
}
function drawMentions() {
  const box = ASK.querySelector('.mentions');
  box.hidden = false;
  box.innerHTML = mention.items
    .map(
      (x, k) =>
        `<div class="mi" role="option" aria-selected="${k === mention.act}" data-mi="${k}"><span class="mn${x.kind === 'endpoint' ? ' mono' : ''}">${esc(x.name)}</span><span class="mw">${esc(x.where || x.kind)}</span></div>`,
    )
    .join('');
}
function pickMention(k) {
  const ta = ASK.querySelector('textarea'),
    x = mention.items[k];
  const name = /\s/.test(x.name) ? x.ref : x.name;
  ta.value = ta.value.slice(0, mention.start) + '@' + name + ' ' + ta.value.slice(mention.end);
  const pos = mention.start + name.length + 2;
  ta.setSelectionRange(pos, pos);
  mention = null;
  ASK.querySelector('.mentions').hidden = true;
  ta.focus();
  renderComposer();
}

function send() {
  const ta = ASK.querySelector('textarea');
  if (busy) {
    busy.abort();
    return;
  }
  const q = ta.value.trim();
  if (!q) return;
  ta.value = '';
  grow(ta);
  ask(q);
}

function onKeydown(e) {
  if (e.target.tagName !== 'TEXTAREA') return;
  if (mention) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      mention.act = (mention.act + (e.key === 'ArrowDown' ? 1 : mention.items.length - 1)) % mention.items.length;
      drawMentions();
      return;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      pickMention(mention.act);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      mention = null;
      ASK.querySelector('.mentions').hidden = true;
      return;
    }
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    closeAsk();
  }
}

function onInput(e) {
  if (e.target.tagName !== 'TEXTAREA') return;
  grow(e.target);
  updateMentions(e.target);
  renderComposer();
}

// ---------------------------------------------------------------- citations and sources talk to the map

const targetOf = el => {
  const ref = el && el.dataset.ref;
  const e = ref && resolve(store.G, ref);
  return e ? (e.t === 'n' ? { t: 'n', id: e.id } : { t: e.t, id: e.id }) : null;
};

function onOver(e) {
  const el = e.target.closest('[data-ref]');
  if (el) {
    setHover(targetOf(el), true);
    ASK.querySelectorAll(`[data-ref="${el.dataset.ref}"]`).forEach(x => x.classList.add('hl'));
  }
}
function onOut(e) {
  const el = e.target.closest('[data-ref]');
  if (el && !el.contains(e.relatedTarget)) {
    setHover(null);
    ASK.querySelectorAll('.hl').forEach(x => x.classList.remove('hl'));
  }
}

function onClick(e) {
  if (e.target.closest('[data-close-ask]')) return closeAsk();
  if (e.target.closest('[data-new]')) {
    if (busy) busy.abort();
    thread = [];
    clearShowing();
    renderThread();
    ASK.querySelector('textarea').focus();
    return;
  }
  if (e.target.closest('[data-send]')) return send();
  const q = e.target.closest('[data-q]');
  if (q) return ask(q.dataset.q);
  const mi = e.target.closest('[data-mi]');
  if (mi) return pickMention(+mi.dataset.mi);
  const show = e.target.closest('[data-show]');
  if (show) {
    const i = +show.dataset.show;
    if (showing === i) return clearShowing();
    return showOnMap(i);
  }
  const el = e.target.closest('[data-ref]');
  if (el) {
    const t = targetOf(el);
    setHover(null);
    if (!t) return;
    if (t.t === 'n') select(t.id, 'list');
    else flyToTerr(t.t, t.id);
    requestRender();
  }
}

/** Wire the panel. Called once from main.js. */
export function init() {
  ASK.addEventListener('click', onClick);
  ASK.addEventListener('keydown', onKeydown);
  ASK.addEventListener('input', onInput);
  ASK.addEventListener('mouseover', onOver);
  ASK.addEventListener('mouseout', onOut);
}

/** Clear the conversation when the dataset changes (refs belong to one graph). */
export function resetAsk() {
  if (busy) busy.abort();
  thread = [];
  showing = -1;
  store.askSet = [];
  if (askOpen()) render();
}
