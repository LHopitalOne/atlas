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
| Sentry | 37 (+3 requests with no route) | 20 / 20 | 0 | 17 / 20 |
| Open edX | 72 (+5 requests with no route) | 61 / 71 | 0 | 8 of the 61 |

The Sentry map also shows **225 links inside sentry**, from its frontend (`static/app`) to its own API routes, found
with `links --within`. No answer key covers them yet, so the page keeps them out of the accuracy numbers, draws them
fainter and folds them into their own section of the links panel.

The accuracy is measured on the answer keys in `eval/sentry` and `eval/openedx`, built by agents that never saw
the link finder. The page says what each number is worth: the finder was developed against the Sentry key, and the
Open edX 61 / 71 came after fixes made while looking at that key's misses (its first, frozen run found 12 / 71 with
31 false links). It was 68 / 71 until `eval/score.py` stopped crediting a key link for a neighbouring route.
Links were found by the finder at `link-finder-held-out` `3f7ca1a` with the SCIP indexes of both sets of
repositories.

The maps show production code only: tests, fixtures, migrations, benches and examples are left out. Of Sentry's
JavaScript frontend (10,000 files) only the 129 files that call its API are on the map. Graphify ran in AST mode (no LLM), so domains
are Graphify's communities and their names are `Community N`.

## Build it

```bash
REPOS=/path/to/demo-repos \
PY=/path/to/python-with-atlas-bridge-links \
SCIP_SENTRY=/path/to/sentry-scip-indexes SCIP_OPENEDX=/path/to/openedx-scip-indexes \
tools/demo/build.sh
```

`REPOS` holds `sentry/ relay/ snuba/ symbolicator/` and `openedx/{openedx-platform,course-discovery,credentials,
frontend-app-learning}/`, checked out at the commits in the answer keys. The steps are `links` (find and score the links, plus
Sentry's frontend-to-API links), `graphify` (mirror each repository's production files into `.demo-work/mirror/` and
run Graphify's AST pass there, so the repositories are not touched), `spec` (draw each map with its links, code and accuracy) and
`page` (one HTML file). `STEPS="spec page" tools/demo/build.sh` reruns only the last two. The output is
**`dist/demo/index.html`**: about 15 MB, 2.1 MB gzipped (GitHub Pages serves it gzipped), and it works offline.

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
