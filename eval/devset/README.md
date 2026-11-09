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
