// Pre-deploy check: every external URL referenced from index.html must resolve.
import { readFile } from 'node:fs/promises';

const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
const EXTERNAL_REF = /\b(?:href|src)="(https?:\/\/[^"]+)"/g;

let failures = 0;
for (const [, url] of html.matchAll(EXTERNAL_REF)) {
  const res = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0 arena-asset-check' } });
  console.log(`ASSET ${res.status} ${url}`);
  if (!res.ok) failures++;
}
process.exitCode = failures ? 1 : 0;
