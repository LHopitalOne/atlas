# Graphify on the link answer keys

The link slides compared Atlas with itself (rules alone, then with `--read`). This measures Graphify on the same answer
keys, so each row has a baseline. Run with Graphify 0.9.106 (the latest release, `pip install graphifyy==0.9.106`),
code only (no LLM), on the repositories [eval/README.md](../README.md) fetches at the commits the keys pin; last run
2026-11-13.

## How

- `build.sh` runs Graphify on every project the way a user would: each separate repository on its own and then
  `graphify merge-graphs` (Sentry's four, Open edX's four), and each single-repository project as one corpus (the dev
  set's monorepos, each small app). It reads every file git tracks in each download (copied, so nothing is written
  into it). Graphify's secret-file filter is turned off, because it drops Open edX's `credentials` repository by name.
- `score.py` is generous, because Graphify has no notion of a request or a route: a key link counts as found when the
  graph has **any edge**, of any relation, in either direction, between a node in a file that sends it and a node in
  the file that receives it (the route's file or its handler's). It also counts every edge that crosses from one
  repository or service folder to another.
- Sanity check: 360 of the 378 links have both their files in Graphify's graph, so a miss means no edge, not a path
  that failed to match. The other 18 are requests to outside hosts (small apps, set 2), which no node stands for.

```bash
export REPOS=~/atlas-eval                # fetched as in eval/README.md
uv venv /tmp/gfy-venv && uv pip install --python /tmp/gfy-venv/bin/python graphifyy==0.9.106
eval/graphify-baseline/build.sh /tmp/gfy-work /tmp/gfy-venv/bin/python     # about 10 minutes, Sentry most of it
python3 eval/graphify-baseline/score.py /tmp/gfy-work
```

## Results

| Set | Links | Graphify | Atlas, rules only | Atlas with `--read` |
| --- | --- | --- | --- | --- |
| Sentry (4 repositories) | 20 | **0** | 20 | 20 |
| Open edX (4 repositories) | 71 | **0** | 61 | 67 |
| Dev set (Immich, Plane, Zulip) | 134 | **21** (0 of the 105 HTTP links) | 94 | 116 |
| Small apps, set 1 | 73 | **0** | 64 | n/a |
| Small apps, set 2 | 80 | **0** | 77 | 78 |
| Sealed test (Authentik, Kolibri, Paperless) | 112 | not measured | 16 | 28 |

- **Between repositories Graphify has no edges at all.** After `merge-graphs`, Sentry's and Open edX's graphs share
  only external library nodes; not one edge joins code in one repository to code in another. Graphify's cross-repository pass (`cross_repo_calls.py`) links a method call to a class declared in another
  repository, for C++, C#, Go, Java, Kotlin, Objective-C, Swift, PHP and TypeScript; an HTTP request is not such a
  call, and Python and Rust are not in its list.
- **The dev set's 21 are all inside one service**: 13 Immich job-queue links, 7 Plane Celery `.delay()` tasks and one
  Zulip queue, where the sending file already imports or calls the handling file (Plane's view imports the task;
  Immich's job service calls the repository that queues). They count under the generous rule; most of Immich's are
  other calls between the same two files, not the job itself. Of the dev set's 105 HTTP links, Graphify finds none.
- **Not measured: the sealed test.** It is kept outside this repository and scored only at milestones; running Graphify
  there means pointing a tool at it, which is left for the next milestone. Everywhere above, Graphify found none of the
  HTTP links, so none is expected there either, but that is an expectation, not a measurement.

Atlas's columns are from [eval/README.md](../README.md). The first run (2026-11-11) read the production files the
demo maps instead of whole repositories; the scores were the same.
