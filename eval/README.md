# Reproduce the link scores

Every answer key in this folder pins the exact commit of the code it was built on. This page lists that code, with a
command to fetch each repository at its commit, and the command that scores Atlas on it. The small apps are in this
repository already; everything else is public on GitHub.

## Setup

```bash
pip install ./bridge                     # Atlas's link finder (Graphify, tree-sitter and its grammars)
export REPOS=~/atlas-eval                # where the code below goes (any folder outside this repository)

# fetch <url> <folder> <commit>: that one commit, without the history (all 15 below: 2.3 GB, about 2 minutes)
fetch() { git init -q "$REPOS/$2" && git -C "$REPOS/$2" fetch -q --depth 1 "$1" "$3" && git -C "$REPOS/$2" checkout -q FETCH_HEAD; }
```

`--read` (the AI reading pass) needs `OPENROUTER_API_KEY` and costs cents per project; every command works without
it, and gives the "rules only" score.

`eval/score.py` judges HTTP links only. The finder also reports Kafka topics and Celery tasks (20 on Sentry, 101 on Open
edX); the scorer counts them apart, as `other_protocols_not_judged`, since these keys cover HTTP.

On 2026-11-13, with the fixes made on Mozilla (below), every rules-only score and the `--read` scores of Open edX,
the dev set, small apps 2, Label Studio and Mozilla were reproduced from these downloads; the fixes moved none but
Mozilla's. Sentry's `--read` score is from an earlier run, and the Graphify column was measured the same day.

## The sets

| Set | Links | Atlas, rules only | `--jev` | `--read` | `--read --jev` | Graphify | Code |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [Sentry](sentry/README.md) | 20 | 20 | 20 | 20 | 20 | 0 | 4 repositories, below |
| [Open edX](openedx/README.md) | 71 | 61 | 61 | 67 | 67 | 0 | 4 repositories, below |
| [Dev set](devset/README.md): Immich, Plane, Zulip | 134 | 94 | 97 | 116 | 116 | 21 | 3 repositories, below |
| [Small apps, set 1](tiny/README.md) | 73 | 64 | 64 | | 64 | 0 | in this repository, `tiny/apps/` |
| [Small apps, set 2](tiny/README.md) | 80 | 77 | 77 | 78 | 78 | 0 | in this repository, `tiny/apps2/` |
| [Label Studio](labelstudio/README.md) (held out) | 15 | 4 | 4 | 4 | 4 | | 2 repositories, below |
| [Mozilla Add-ons](mozilla/README.md) (practice, was held out) | 41 | 1 | 1 | 32, and 4 false | 32, and 4 false | | 2 repositories, below |
| Sealed test: Authentik, Kolibri, Paperless | 112 | 16 | | 28 | | | not published |

The sealed test is kept outside this repository on purpose: a key anyone can read stops being a fair test, so it is
scored only at milestones. The Graphify column is from [graphify-baseline](graphify-baseline/README.md).

**Read the table with overfitting in mind.** Sentry, Open edX, the dev set, the small apps and (since 2026-11-13)
Mozilla are sets the finder was fixed on when it missed something, so their scores show how it does on code already
studied.
Only Label Studio and the sealed test measure new code, and they score far lower: 4 / 15, and 16 / 112 with the rules
alone (28 with `--read`). The sealed score above predates the Mozilla fixes; it is rerun at the next milestone. The
finder links wrongly rarely (4 false links on Mozilla, 1 on Open edX with `--read`, none elsewhere); what it lacks on
new code is coverage of the many ways code writes a request.

`--jev` (run 2026-11-13) asks Jev, a decision model on OpenRouter, to pick a route for each request the rules found
but left open, among the routes the code offers; it never invents one. It added 3 links, all Zulip's, and no false
ones; on top of `--read` it added none, since the reading pass had already settled those requests. It cost under a
cent for every set together.

### Sentry

| Repository | Commit |
| --- | --- |
| [getsentry/sentry](https://github.com/getsentry/sentry/tree/c69ccf85ab98d619e650c31bb1daed839deb5d2b) | `c69ccf8` |
| [getsentry/relay](https://github.com/getsentry/relay/tree/de080b7053b5e59826af76528f682fe51fa2ed75) | `de080b7` |
| [getsentry/snuba](https://github.com/getsentry/snuba/tree/bd2c5d02e90ace8521074d94ccb22aa4940d966f) | `bd2c5d0` |
| [getsentry/symbolicator](https://github.com/getsentry/symbolicator/tree/2abba9028ca896c489a56fc4ead86383a7301b04) | `2abba90` |

```bash
fetch https://github.com/getsentry/sentry sentry c69ccf85ab98d619e650c31bb1daed839deb5d2b
fetch https://github.com/getsentry/relay relay de080b7053b5e59826af76528f682fe51fa2ed75
fetch https://github.com/getsentry/snuba snuba bd2c5d02e90ace8521074d94ccb22aa4940d966f
fetch https://github.com/getsentry/symbolicator symbolicator 2abba9028ca896c489a56fc4ead86383a7301b04

python3 -m atlas_bridge links sentry=$REPOS/sentry relay=$REPOS/relay snuba=$REPOS/snuba \
  symbolicator=$REPOS/symbolicator --alias upstream=sentry -o sentry-links.json
python3 eval/score.py eval/sentry/answer-key.json sentry-links.json
```

### Open edX

| Repository | Commit |
| --- | --- |
| [openedx/openedx-platform](https://github.com/openedx/openedx-platform/tree/db5bfda81ec02ca78f24932bafa79c8f43e5ffa7) | `db5bfda` |
| [openedx/course-discovery](https://github.com/openedx/course-discovery/tree/e0eadcd2c2411832c7e51085c901f4e9e8e293d0) | `e0eadcd` |
| [openedx/credentials](https://github.com/openedx/credentials/tree/8bb9b5f03e9b6d56a0e6dc590c79680f250d6090) | `8bb9b5f` |
| [openedx/frontend-app-learning](https://github.com/openedx/frontend-app-learning/tree/7ae8423179b4a2edfd494b1fab77087f810bee1f) | `7ae8423` |

```bash
fetch https://github.com/openedx/openedx-platform openedx-platform db5bfda81ec02ca78f24932bafa79c8f43e5ffa7
fetch https://github.com/openedx/course-discovery course-discovery e0eadcd2c2411832c7e51085c901f4e9e8e293d0
fetch https://github.com/openedx/credentials credentials 8bb9b5f03e9b6d56a0e6dc590c79680f250d6090
fetch https://github.com/openedx/frontend-app-learning frontend-app-learning 7ae8423179b4a2edfd494b1fab77087f810bee1f

python3 -m atlas_bridge links openedx-platform=$REPOS/openedx-platform course-discovery=$REPOS/course-discovery \
  credentials=$REPOS/credentials frontend-app-learning=$REPOS/frontend-app-learning \
  --alias lms=openedx-platform --alias studio=openedx-platform \
  --alias catalog=course-discovery --alias discovery=course-discovery --alias credentials=credentials \
  -o openedx-links.json                  # add --read for the second column
python3 eval/score.py eval/openedx/answer-key.json openedx-links.json
```

### Dev set

| Repository | Commit |
| --- | --- |
| [immich-app/immich](https://github.com/immich-app/immich/tree/dae37df1a70c21493acdafd85bad8ab69e6b390d) | `dae37df` |
| [makeplane/plane](https://github.com/makeplane/plane/tree/618d0eb74658329a6f6e92434ac54231422c5b96) | `618d0eb` |
| [zulip/zulip](https://github.com/zulip/zulip/tree/f0f02bcb08cb99ea161baec9a6c2edd008217dda) | `f0f02bc` |

```bash
fetch https://github.com/immich-app/immich immich dae37df1a70c21493acdafd85bad8ab69e6b390d
fetch https://github.com/makeplane/plane plane 618d0eb74658329a6f6e92434ac54231422c5b96
fetch https://github.com/zulip/zulip zulip f0f02bcb08cb99ea161baec9a6c2edd008217dda

python3 eval/tiny/run.py eval/devset /tmp/devset-out --repos $REPOS              # add: -- --read
```

### Small apps

Their code is in `tiny/apps/` and `tiny/apps2/`; each app's `run.sh` starts its services and exercises every link.

```bash
python3 eval/tiny/run.py eval/tiny/apps /tmp/apps-out
python3 eval/tiny/run.py eval/tiny/apps2 /tmp/apps2-out                         # add: -- --read
```

### Label Studio (held out) and Mozilla Add-ons (practice)

| Repository | Commit |
| --- | --- |
| [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio/tree/e638bb569a20d1361b6ce6f719d06f87747e94e1) | `e638bb5` |
| [HumanSignal/label-studio-ml-backend](https://github.com/HumanSignal/label-studio-ml-backend/tree/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42) | `a13c5fb` |
| [mozilla/addons-server](https://github.com/mozilla/addons-server/tree/65a56ea495b315b9887c7f7734e408d6c444b537) | `65a56ea` |
| [mozilla/addons-frontend](https://github.com/mozilla/addons-frontend/tree/b2ed6ceaa35c85c86109766e345bf25223c71a08) | `b2ed6ce` |

```bash
fetch https://github.com/HumanSignal/label-studio label-studio e638bb569a20d1361b6ce6f719d06f87747e94e1
fetch https://github.com/HumanSignal/label-studio-ml-backend label-studio-ml-backend a13c5fb6e7766c6ce9007c0c77d44d17239ffd42
fetch https://github.com/mozilla/addons-server addons-server 65a56ea495b315b9887c7f7734e408d6c444b537
fetch https://github.com/mozilla/addons-frontend addons-frontend b2ed6ceaa35c85c86109766e345bf25223c71a08

python3 -m atlas_bridge links label-studio=$REPOS/label-studio label-studio-ml-backend=$REPOS/label-studio-ml-backend \
  --alias ml=label-studio-ml-backend -o labelstudio-links.json
python3 eval/score.py eval/labelstudio/answer-key.json labelstudio-links.json
python3 -m atlas_bridge links addons-server=$REPOS/addons-server addons-frontend=$REPOS/addons-frontend \
  --alias api=addons-server -o mozilla-links.json
python3 eval/score.py eval/mozilla/answer-key.json mozilla-links.json
```

Label Studio sends most of its requests where the plain commands cannot see a URL: 11 of its 15 go through
`label_studio_sdk`, a third repository. `--read` (run 2026-11-13, $0.33) found none of them; its README explains
each miss and what `--library` and SCIP indexes add.

Mozilla was held out until 2026-11-13, when the finder was fixed on what it missed there, so it is now a practice
set like the dev set. 39 of its 41 links go through `callApi({ endpoint: ... })`, a wrapper that takes the path as
an object property, so the rules alone find 1; `--read` finds 32. Four general fixes did it, each checked on every
other set (none moved): the reading pass now takes a URL that starts with several expressions
(`{apiHost}{apiPath}{version}/addons/search/`) and a wrapper whose path its callers pass (`/{endpoint}/`); the Django
reader follows a list a function is given (`*get_versioned_api_routes('v5', v5_api_urls)`), routers imported from
another module and drf-nested-routers; and when the same route is served under several API versions, a request is
matched to the newest. The 4 false links are page links in `AddonMoreInfo/index.js` (`/addon/{slug}/license` and the
like) that fit server pages of the same shape; the 9 still missed are the 7 ratings requests, autocomplete and
logout, which the model did not read as requests.

## Also here

- [scip-edges](scip-edges/README.md): a blind audit of the code-graph edges SCIP adds to Graphify's, on Sentry and
  Open edX.
- [graphify-baseline](graphify-baseline/README.md): Graphify on the same keys, from the same downloads (`REPOS`).
