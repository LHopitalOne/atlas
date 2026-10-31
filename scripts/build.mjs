// Build the single-file artifact: bundle src/ with esbuild, inline it into src/index.html with the self graph.
// Usage: node scripts/build.mjs [--offline]   (--offline also inlines d3-hierarchy so the file works with no network)
import { build } from 'esbuild';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';

const offline = process.argv.includes('--offline');
const graphArg = process.argv.find(a => a.startsWith('--graph='));
const graphFile = graphArg ? graphArg.slice('--graph='.length) : 'generated/self-graph.json';
const result = await build({
  entryPoints: ['src/main.js'],
  bundle: true,
  format: 'iife',
  globalName: 'Atlas',
  target: 'es2020',
  write: false,
  legalComments: 'none',
});
const bundle = result.outputFiles[0].text.replaceAll('</script', '<\\/script');
if (!existsSync(graphFile)) throw new Error(`Graph file not found: ${graphFile}`);
const graph = readFileSync(graphFile, 'utf8').replaceAll('</', '<\\/');
const sourceFile = 'generated/self-source.json';
const source = !graphArg && existsSync(sourceFile) ? readFileSync(sourceFile, 'utf8').replaceAll('</', '<\\/') : '{}';

// one pass over the template: inserted text is never scanned again (the source bundle contains index.html itself)
const parts = { __SELF_GRAPH__: graph, __SELF_SOURCE__: source, __BUNDLE__: bundle };
let html = readFileSync('src/index.html', 'utf8').replace(/__SELF_GRAPH__|__SELF_SOURCE__|__BUNDLE__/g, m => parts[m]);
if (offline) {
  const d3 = readFileSync('node_modules/d3-hierarchy/dist/d3-hierarchy.min.js', 'utf8').replaceAll(
    '</script',
    '<\\/script',
  );
  html = html
    .replace(
      /<script src="https:\/\/cdn\.jsdelivr\.net\/npm\/d3-hierarchy@[^"]+"><\/script>/,
      () => `<script>/* d3-hierarchy 3.1.2, ISC license */\n${d3}\n</script>`,
    )
    .replace('<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>\n', '');
}
mkdirSync('dist', { recursive: true });
const outArg = process.argv.find(a => a.startsWith('--out='));
const out = outArg ? outArg.slice(6) : offline ? 'dist/atlas-offline.html' : 'dist/atlas.html';
writeFileSync(out, html);
console.log(`${out}  ${(html.length / 1024).toFixed(0)} KB`);
