# The demo page

One static HTML file with two real maps, **Sentry** (sentry, relay, snuba, symbolicator) and **Open edX**
(openedx-platform, course-discovery, credentials, frontend-app-learning). Graphify maps each repository's production
code; the link finder adds every HTTP request one repository sends to a route another serves. Every link can be
clicked and proven: the line that sends the request and the route line that serves it, with code, GitHub links at
the pinned commits, and a badge for how it is proven. Selecting an endpoint, a file or a repository shows what calls
it from other repositories, which is what breaks if it changes.

## What is on it

| Map | HTTP links between repositories | Production links found | False links | Confirmed by SCIP |
| --- | --- | --- | --- | --- |
| Sentry | 49 (+5 requests with no route) | 20 / 20 | 0 | 17 / 20 |
| Open edX | 85 (+5 requests with no route) | 67 / 71 (61 with the rules alone) | 1 | 8 of the 67 |

The Sentry map also shows **235 links inside sentry**, from its frontend (`static/app`) to its own API routes, found
with `links --within`. No answer key covers them yet, so the page keeps them out of the accuracy numbers, draws them
fainter and folds them into their own section of the links panel.

The accuracy is measured on the answer keys in `eval/sentry` and `eval/openedx`, built by agents that never saw
the link finder. The page says what each number is worth: the finder was developed against the Sentry key, and the
Open edX 61 / 71 (the rules alone) came after fixes made while looking at that key's misses (its first, frozen run
found 12 / 71 with 31 false links); the AI reading pass (`--read`) takes it to 67 / 71, with one false link. It was
68 / 71 until `eval/score.py` stopped crediting a key link for a neighbouring route. Links were found by the finder
at `e199484` with `--read` and the SCIP indexes of both sets of repositories, and the maps also carry the code-graph
edges those indexes add to Graphify's.

The maps show production code only: tests, fixtures, migrations, benches and examples are left out. Of Sentry's
JavaScript frontend (10,000 files) only the 134 files that call its API are on the map. Graphify ran in AST mode (no LLM), so domains
are Graphify's communities and their names are `Community N`.

## The welcome tour

The page is built with `--tour`, so a first-time viewer gets a short tour: the page dims and the parts that matter stay
lit while a card explains them. It welcomes them to Sentry with a card over the whole map (the links panel waits for
its own step), waits for them to click a link and lights both its proof and the link on the map, switches to
Open edX, and opens Ask Atlas with one sample question whose answer is drawn as a diagram (a route across three
repositories; the questions are `TOUR.ask` in `src/config.js`). Skip or Escape ends it, it does not come back on its
own, and the `?` button in the toolbar plays it again.

## Build it

```bash
REPOS=/path/to/demo-repos \
PY=/path/to/python-with-atlas-bridge-links \
SCIP_SENTRY=/path/to/sentry-scip-indexes SCIP_OPENEDX=/path/to/openedx-scip-indexes \
READ=1 tools/demo/build.sh                          # READ=1 needs OPENROUTER_API_KEY
```

The SCIP indexes come from `python3 -m atlas_bridge index <name>=<folder> ... -o <folder>`, about 5 minutes for
both sets. openedx-platform's TypeScript index fails on a symlink into packages a fresh download does not have; the
run reports it, writes every other index, and exits with an error naming what it skipped.

`REPOS` holds `sentry/ relay/ snuba/ symbolicator/` and `openedx/{openedx-platform,course-discovery,credentials,
frontend-app-learning}/`, checked out at the commits in the answer keys. The steps are `links` (find and score the links, plus
Sentry's frontend-to-API links), `graphify` (mirror each repository's production files into `.demo-work/mirror/` and
run Graphify's AST pass there, so the repositories are not touched), `spec` (draw each map with its links, code and accuracy) and
`page` (one HTML file). `STEPS="spec page" tools/demo/build.sh` reruns only the last two. The output is
**`dist/demo/index.html`**: about 19 MB, 2.8 MB gzipped (GitHub Pages serves it gzipped), and it works offline.

`SPLIT=1 STEPS=page tools/demo/build.sh` writes the same page to **`dist/demo-split/`** with each map in its own
file (`maps/sentry.json` 15 MB, `maps/openedx.json` 3.7 MB), downloaded when that map is first shown. Use it for a
host that caps one file's size, such as a Claude artifact (16 MB a file). It needs a web server: a browser opened on
the file itself cannot fetch the maps beside it.

## Publish it on GitHub Pages

Nothing below has been run; each step publishes.

1. Make sure the answer keys the page links to are on the default branch (`eval/sentry/README.md`,
   `eval/openedx/README.md`), or rebuild with
   `KEY_BASE=https://github.com/<owner>/<repo>/blob/<branch>/ STEPS="spec page" tools/demo/build.sh`.
   GitHub Pages on a free plan needs a public repository.
2. Put the file on a `gh-pages` branch, from a separate worktree so your checkout is untouched (git 2.42 or later):

   ```bash
   git worktree add --orphan -b gh-pages ../atlas-pages
   cp dist/demo/index.html ../atlas-pages/index.html
   touch ../atlas-pages/.nojekyll
   git -C ../atlas-pages add index.html .nojekyll
   git -C ../atlas-pages commit -m "Demo: Sentry and Open edX maps with proven HTTP links"
   git -C ../atlas-pages push -u origin gh-pages
   ```

3. Turn Pages on for that branch (or in the repository's Settings, Pages, "Deploy from a branch", `gh-pages`, `/`):

   ```bash
   gh api -X POST repos/<owner>/<repo>/pages -f 'source[branch]=gh-pages' -f 'source[path]=/'
   ```

4. The page is at `https://<owner>.github.io/<repo>/` after a minute. `#sentry` and `#openedx` open each map; any
   view can be shared, since the selection lives in the hash (`#sentry-node-80899`).

To update it later, rebuild, copy the file into `../atlas-pages`, commit and push again.

## Host it on Vercel

On Vercel, Ask Atlas can use the model without the viewer giving a key: two functions stand in for `atlas serve`'s
local helper (`/api/llm/ping`, `/api/llm/chat/completions`), and the OpenRouter key stays on Vercel. The page itself
is unchanged; it tries `./api/llm` first, as it does under `atlas serve`.

1. Build the folder (from the specs already in `.demo-work`; rerun the other steps first if they changed):

   ```bash
   VERCEL=1 STEPS=page REPOS=/path/to/demo-repos tools/demo/build.sh
   ```

   It writes **`dist/demo-vercel/`**: the split page (`index.html`, `maps/`) plus `tools/demo/vercel/` (`api/llm/`,
   `lib/llm-proxy.js`, `vercel.json`, a `package.json` that only marks the files as ES modules). A rebuild keeps
   `.vercel/`, the project link made in step 2.

2. Link that folder to a Vercel project (once). Every `vercel` command below runs with `--cwd dist/demo-vercel`, so
   it acts on this project and not on one for the repository root:

   ```bash
   vercel link --cwd dist/demo-vercel
   ```

3. Give the project its key, for production and preview both (you type it; use an OpenRouter key made for this demo,
   so it can be revoked on its own). One command per environment; for preview, press Enter at the branch question
   to cover every branch:

   ```bash
   vercel env add OPENROUTER_API_KEY production --cwd dist/demo-vercel
   vercel env add OPENROUTER_API_KEY preview --cwd dist/demo-vercel
   ```

   A key added or changed here only reaches deployments made after it, so deploy again after any change.

4. Deploy a preview, try Ask on it, then deploy to production:

   ```bash
   vercel deploy --cwd dist/demo-vercel
   vercel deploy --prod --cwd dist/demo-vercel
   ```

   If Ask asks the viewer for an OpenRouter key, `/api/llm/ping` answered 404: the deployment has no key, so check
   step 3 and deploy again.

What the functions do: every request must come from the demo's own page, meaning its `Origin` header (or `Referer`,
which a same-origin GET sends instead) names the host it was sent to; that holds on any preview or production URL.
`ALLOWED_HOSTS` (comma-separated) accepts more page hosts, but only for a page that reaches `/api` on its own origin,
through a proxy that sends a different `Host`: the functions send no CORS headers and answer no preflight, so a page
on another site cannot call them (its JSON POST is blocked before the host check runs). The model is always `meta/muse-ember` whatever the request
asks for (`MODEL` in `lib/llm-proxy.js`, kept equal to `ASK_MODEL` by `test/vercel.test.js`), bodies over 4,000,000
bytes or not JSON are refused, and OpenRouter's status and body come back as they are. There is no token or spending
cap; set a credit limit on the key in OpenRouter if you want one.

What the check does not stop: it keeps other websites from spending the key through their visitors' browsers, but a
script outside a browser can send any `Origin` it likes, so anyone who finds the URL can still call the model.
Revoke the key when the demo is over.

`vercel.json` sets no framework, Fluid compute, `maxDuration` 300 s for the functions (the Hobby maximum with Fluid
compute), `index.html` uncached and `maps/*.json` cached for an hour (their names do not change between builds, so
longer would show an old map with a new page). Sources: [function duration](https://vercel.com/docs/functions/configuring-functions/duration),
[limits](https://vercel.com/docs/functions/limitations) (4.5 MB request body),
[Node.js runtime](https://vercel.com/docs/functions/runtimes/node-js) (`export function GET(request)`, ES modules
need `"type": "module"`), [vercel.json](https://vercel.com/docs/project-configuration/vercel-json).
