# Development set: real projects to learn from

Three large open-source projects with the kinds of code the sealed lockbox needs (a project-wide request layer,
generated API clients, background jobs, a frontend calling its own backend), used to find and fix general misses.
They are a development set: the finder is improved by looking at their misses. The honest number is the sealed
lockbox (kept outside this repository), scored only at milestones.

| Project | Commit | Send sites in the code | Sampled links |
| --- | --- | --- | --- |
| Immich (NestJS server, SvelteKit web app through a generated SDK, Python ML service) | dae37df | 498 | 46 |
| Plane (Django API, Next.js apps, shared TypeScript service packages, Celery) | 618d0eb | 656 | 41 |
| Zulip (Django REST API, TypeScript web client, Tornado, RabbitMQ workers) | f0f02bc | 267 | 47 |

Each key was built like the lockbox: an agent that never saw the finder listed every production send site, a fixed
rule drew 40 of them (the first 40 by FNV-1a hash of `file:line`), a second agent traced each to its receiver and a
third tried to refute every link. Each `TRUTH.json` names where its code is (`root`) and its services' folders.

```bash
python3 eval/tiny/run.py eval/devset /tmp/devset-out --python bridge/.venv/bin/python
```

A sampled key judges only the links the finder makes at the call sites it covers; links at other sites are counted
as unjudged, not false.

| Finder | Immich | Plane | Zulip | All | False links (judged) |
| --- | --- | --- | --- | --- | --- |
| commit f9d3d98 | 0 / 46 | 32 / 41 | 0 / 47 | 32 / 134 | 0 |
| + background tasks, route helpers, JavaScript request helpers, NestJS and generated clients | 24 / 46 | 39 / 41 | 31 / 47 | **94 / 134** | 0 |
| + `--read` (Muse Ember reads the files the extractors leave unexplained; the code checks every claim) | 36 / 46 | 41 / 41 | 39 / 47 | **116 / 134** | 0 |

The four mechanisms came from a diagnosis of every miss (by agents that saw the code, the key and what the finder
extracted, not the finder's code), each needed by at least two of the three projects except generated clients, and
each implemented in its own branch and reviewed by a second agent whose job was to reject rules naming these
projects rather than a language, library or framework:

- Background tasks (a new `task` protocol): Celery tasks (`@shared_task`, `.delay()`, `.apply_async()`, signatures,
  `send_task`) and BullMQ queues and workers, linked within the repository that sends and handles them.
- Route helpers: a function returning Django's `path()`/`re_path()` built from its parameters declares a route at each
  call; methods given as keyword arguments named like HTTP methods; URLconf lists combined with `+`/`+=`.
- JavaScript request helpers: jQuery `$.ajax`/`$.get`/`$.post`, helpers reading `options.url` from their parameter, a
  request helper passed by reference, a URL variable assigned in branches.
- NestJS controllers with the global prefix, the oazapfts runtime of generated clients, and imports followed into the
  monorepo's own packages.

Links outside every key are not judged by the sampled keys; a fixed sample of them is audited separately.

With `--read`, a model on OpenRouter reads each file that looks like it sends or serves more than the extractors found, and lists its requests, helpers and routes; the code keeps a claim only when the line,
every fixed word of the path, any host and the channel's name are written in the file, then matches it with the same
rules. Three of those checks came from this set's misses, as the set is meant for (a channel held in a variable, a
relay that takes every event, a list of jobs sent at once); none names a project. It cost $0.15 (Immich), $0.50 (Plane) and $0.52 (Zulip) on a first run; answers are cached, so a rerun is free.
Its answers vary a little between first runs (Immich: 34 to 43 of 46), so the row above is one run, not a best of.
