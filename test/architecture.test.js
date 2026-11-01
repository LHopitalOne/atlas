// Guards the structure documented in CLAUDE.md and docs/ARCHITECTURE.md.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, dirname, resolve } from 'node:path';

const SRC = resolve('src');
const files = d =>
  readdirSync(d).flatMap(f => {
    const p = join(d, f);
    return statSync(p).isDirectory() ? files(p) : p.endsWith('.js') ? [p] : [];
  });
const modules = files(SRC).map(p => ({ path: relative(SRC, p).replaceAll('\\', '/'), code: readFileSync(p, 'utf8') }));
const importsOf = m =>
  [...m.code.matchAll(/^import [^;]*? from '([^']+)';/gm)].map(x =>
    relative(SRC, resolve(SRC, dirname(m.path), x[1])).replaceAll('\\', '/'),
  );
const layer = p => p.split('/')[0].replace('.js', '');

test('pure layers (model, graph) import only pure modules', () => {
  const pure = /^(model|graph)\/|^util\/(math|format)\.js$/;
  for (const m of modules.filter(x => /^(model|graph)\//.test(x.path)))
    for (const i of importsOf(m)) assert.match(i, pure, `${m.path} imports ${i}`);
});

test('the question-answering core (ask tools, local answers, formatting) stays pure', () => {
  const pure =
    /^(model|graph|ask\/(tools|local|format))\/?|^(model|graph)\/|^util\/(math|format)\.js$|^ask\/(tools|local|format)\.js$/;
  for (const m of modules.filter(x => /^ask\/(tools|local|format)\.js$/.test(x.path)))
    for (const i of importsOf(m)) assert.match(i, pure, `${m.path} imports ${i}`);
});

test('util and config import nothing', () => {
  for (const m of modules.filter(x => /^util\/|^config\.js$/.test(x.path))) assert.deepEqual(importsOf(m), [], m.path);
});

test('the renderer never imports the UI', () => {
  for (const m of modules.filter(x => layer(x.path) === 'render'))
    for (const i of importsOf(m))
      assert.notEqual(layer(i), 'ui', `${m.path} imports ${i}; subscribe with onFrameDrawn instead`);
});

test('modules do no work at import time: top level only declares', () => {
  const allowed =
    /^(import|export (function|const|let|class|async function)|function|const|let|class|async function|\/\/|\/\*|\*|\s|\}|$)/;
  for (const m of modules.filter(x => x.path !== 'main.js')) {
    let inTemplate = false; // skip the inside of template strings (e.g. GLSL sources)
    m.code.split('\n').forEach((line, n) => {
      if (!inTemplate && /^[A-Za-z_$]/.test(line))
        assert.match(line, allowed, `${m.path}:${n + 1} runs code at import: ${line.slice(0, 60)}`);
      if ((line.match(/(?<!\\)`/g) || []).length % 2) inTemplate = !inTemplate;
    });
  }
});

test('every module says what it is for', () => {
  for (const m of modules) assert.match(m.code, /^\/\*\*|^\/\//, `${m.path} needs a header comment`);
});
