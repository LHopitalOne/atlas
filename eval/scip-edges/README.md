# SCIP edges: how accurate, and what they add to Graphify's graph

A blind audit of the code-graph edges on Sentry (sentry, relay, snuba, symbolicator) and Open edX
(openedx-platform, course-discovery, credentials, frontend-app-learning), at the commits in `../../.demo-work`'s
mirrors, with the SCIP indexes the demo uses. Run on 2026-11-11 at bridge commit 18b6a63.

## How

- `sample.py` reads each project's Graphify graphs, adds the SCIP edges (`usecases/scipedges.py`) and draws, by a
  fixed hash, 25 edges per project from each of four buckets: Graphify's extracted edges, Graphify's guesses
  (inferred) that SCIP also shows, Graphify's guesses SCIP does not show, and edges only SCIP adds. It also draws 15
  Python functions per project.
- Five agents that never saw the bridge judged the 200 edges, shuffled, without being told where any came from: does
  the source really use this exact definition (following imports, receiver types and inheritance)? Each verdict cites
  file:line (`results/edges*.json`).
- Two agents listed every use of a same-repository definition inside the 30 functions (`results/functions*.json`).
  Recall counts each distinct (function, definition) pair once, and is also given for the definitions that are nodes on
  the map (Graphify makes no node for most module constants, so no edge can reach them).
- `score.py` (precision; graph precision weighs each bucket by its size from `sizes.json`).

## Results

| Edges | Judged | Correct |
| --- | --- | --- |
| Graphify extracted | 50 | 47 (94%) |
| Graphify guesses SCIP shows (now marked extracted) | 50 | 50 (100%) |
| Graphify guesses SCIP does not show (kept as guesses) | 50 | 44 (88%) |
| Added by SCIP | 50 | 49 (98%) |

| Project | Graphify | Graphify + SCIP |
| --- | --- | --- |
| Sentry: edges, share correct | 192,606, ~90% (~172,800 true) | 263,010, ~92% (~243,200 true) |
| Open edX: edges, share correct | 41,262, ~99% (~40,800 true) | 57,650, ~98% (~56,600 true) |
| Real uses found (119 in 30 functions) | 64 (54%) | 93 (78%) |
| ... of those whose target is a node on the map (99) | 64 (65%) | 93 (94%) |

What the wrong ones were: Graphify's 3 wrong extracted edges are name confusions (the builtin `Exception` taken for
Sentry's `interfaces.exception.Exception`, twice; a Rust enum variant taken for a use of its enum). SCIP's 1 wrong
edge gave a use to the wrong method of several named `get` in one file. Of Graphify's guesses SCIP does not show, 6
of 50 are wrong (a local variable or another module's `ValidationError` with the same name); the other 44 are real
uses SCIP misses, so they are kept, not dropped.

Limits: 50 edges per bucket (a 98% has a 95% interval of about 89-100%); the judges are language-model agents whose
every verdict cites a line, spot-checked by hand; recall is measured on Python functions only, against the uses the
agents listed.
