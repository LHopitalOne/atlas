// Exercise the web app's client code from Node: same modules the browser bundle uses.
import { readFile } from 'node:fs/promises';
import { setDefaultAutoSelectFamilyAttemptTimeout } from 'node:net';
import { join } from 'node:path';

import { configureApi } from '../src/api';
import { askForSummary, loadFrontPage, openStory, waitForSummary } from '../src/newsroom';

const log = (msg: string) => console.log(`drive: ${msg}`);

// The default 250ms happy-eyeballs attempt timeout is too tight on a busy machine.
setDefaultAutoSelectFamilyAttemptTimeout(2000);

async function fetchWithRetry(url: URL, attempts = 5): Promise<Response> {
  for (let i = 1; ; i++) {
    try {
      return await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0 newsroom-drive' }, signal: AbortSignal.timeout(8000) });
    } catch (err) {
      if (i >= attempts) throw err;
      log(`retrying ${url} (${String(err)})`);
      await new Promise((resolve) => setTimeout(resolve, 1000 * i));
    }
  }
}

/** Load the outside assets/links that index.html references, like a browser (or a link checker) would. */
async function checkHtmlLinks(): Promise<void> {
  const html = await readFile(join(import.meta.dirname, '..', 'index.html'), 'utf8');
  const ids: Record<string, string> = { stylesheet: 'H01', anchor: 'H02' };
  const stylesheet = html.match(/<link rel="stylesheet" href="([^"]+)"/)?.[1];
  const anchor = html.match(/<a href="(https:[^"]+)"/)?.[1];
  for (const [kind, href] of [['stylesheet', stylesheet], ['anchor', anchor]] as const) {
    if (!href) throw new Error(`index.html has no ${kind}`);
    const url = new URL(href);
    const res = await fetchWithRetry(url);
    if (!res.ok) throw new Error(`${href} -> ${res.status}`);
    console.log(`RECV ${ids[kind]} GET ${url.host}${url.pathname} (caller web index.html, ${res.status})`);
  }
}

async function main(): Promise<void> {
  configureApi(process.env.NEWSROOM_API_URL);
  await checkHtmlLinks();

  const stories = await loadFrontPage(8);
  log(`front page has ${stories.length} stories`);
  const pick = stories.find((s) => s.kids && s.kids.length > 0) ?? stories[0];
  if (!pick) throw new Error('no stories');

  const story = await openStory(pick.id);
  log(`opened ${story.id}: ${story.title}`);
  const job = await askForSummary(story.id);
  log(`queued job ${job.job_id}`);
  const summary = await waitForSummary(story.id);
  log(`summary (${summary.comment_count} comments): ${summary.summary}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
