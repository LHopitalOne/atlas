# Fourth test: HTTP links between Label Studio and its ML backend

The third held-out test. The finder was frozen before the key was built (the same code as the
[Mozilla](../mozilla/README.md) run: commit `857f312` plus the uncommitted Open edX fixes, content hash
`2760c9bbc3d7`) and run once; the score below is that run, unchanged.

| Repository | Commit |
| --- | --- |
| label-studio (Django + DRF, React/TypeScript in `web/`) | [e638bb5](https://github.com/HumanSignal/label-studio/tree/e638bb569a20d1361b6ce6f719d06f87747e94e1) |
| label-studio-ml-backend (Flask, plus the example backends in `label_studio_ml/examples/`) | [a13c5fb](https://github.com/HumanSignal/label-studio-ml-backend/tree/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42) |

Links run both ways: Label Studio calls the ML server it is connected to (health, setup, predictions, training
webhooks), and the ML backends call Label Studio back to download task files and read or write tasks, projects and
predictions. The second direction goes entirely through `label_studio_sdk`, a third repository
([label-studio-sdk @ f2a9c5b](https://github.com/HumanSignal/label-studio-sdk/tree/f2a9c5ba25d34d3878774988c979755ac81ed7be))
that is not in the set: the request is caused by code in the ML backend but sent by code in the SDK.

## How it was made

As for the earlier keys, and with the rules written before any agent ran: one agent per direction listed every
request one repository sends to the other and traced it to the serving route, without seeing the finder. The SDK was
given as reference only, to learn which request an SDK call sends; such links are tagged `library`. The example ML
backends count as production (they are shipped backends with their own images). A skeptic agent tried to refute
each link: 15 of 16 held and it found none missing. It moved the 16th (`PATCH /api/tasks/{pk}/` from the Deepgram
example) to excluded because that code calls a method no class defines and fails before sending, and it dropped call
sites in `ls_io.py`, which nothing calls. A script checked that all 192 cited lines exist. A machine-built and
machine-checked key, not a human review.

## Links (15, all production)

| Id | Request | Sent by | Served by | Called from |
| --- | --- | --- | --- | --- |
| L01 | `GET /health` | own code | [label_studio_ml/api.py:136](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/api.py#L136) | [label_studio/ml/api_connector.py:234](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/ml/api_connector.py#L234) (+4) |
| L02 | `POST /predict` | own code | [label_studio_ml/api.py:34](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/api.py#L34) | [label_studio/ml/api_connector.py:231](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/ml/api_connector.py#L231) (+6) |
| L03 | `POST /setup` | own code | [label_studio_ml/api.py:92](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/api.py#L92) | [label_studio/ml/api_connector.py:242](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/ml/api_connector.py#L242) (+4) |
| L04 | `POST /webhook` | own code | [label_studio_ml/api.py:117](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/api.py#L117) | [label_studio/ml/api_connector.py:198](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/ml/api_connector.py#L198) (+7) |
| L05 | `POST /api/predictions/` | label_studio_sdk | [label_studio/tasks/urls.py:11](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/tasks/urls.py#L11) | [label_studio_ml/examples/yolo/cli.py:69](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/examples/yolo/cli.py#L69) |
| L06 | `GET /api/projects/{pk}/` | label_studio_sdk | [label_studio/projects/urls.py:20](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/projects/urls.py#L20) | [label_studio_ml/examples/bert_classifier/model.py:129](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/examples/bert_classifier/model.py#L129) (+5) |
| L07 | `GET /api/tasks/` | label_studio_sdk | [label_studio/tasks/urls.py:15](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/tasks/urls.py#L15) | [label_studio_ml/examples/bert_classifier/model.py:130](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/examples/bert_classifier/model.py#L130) (+4) |
| L08 | `GET /api/tasks/{pk}/` | label_studio_sdk | [label_studio/tasks/urls.py:16](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/tasks/urls.py#L16) | [label_studio_ml/examples/yolo/cli.py:123](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/examples/yolo/cli.py#L123) |
| L09 | `POST /api/token/refresh/` | label_studio_sdk | [label_studio/jwt_auth/urls.py:10](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/jwt_auth/urls.py#L10) | [label_studio_ml/model.py:264](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/model.py#L264) (+4) |
| L10 | `GET /api/users/` | label_studio_sdk | [label_studio/users/urls.py:14](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/users/urls.py#L14) | [label_studio_ml/examples/watsonx_llm/data_transfer_app.py:113](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/examples/watsonx_llm/data_transfer_app.py#L113) |
| L11 | `GET /api/version/` | label_studio_sdk | [label_studio/core/urls.py:71](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/core/urls.py#L71) | [label_studio_ml/examples/bert_classifier/model.py:128](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/examples/bert_classifier/model.py#L128) (+4) |
| L12 | `GET /data/local-files/` | label_studio_sdk | [label_studio/io_storages/urls.py:220](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/io_storages/urls.py#L220) | [label_studio_ml/model.py:291](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/model.py#L291) (+29) |
| L13 | `GET /data/upload/{filename}` | label_studio_sdk | [label_studio/data_import/urls.py:24](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/data_import/urls.py#L24) | [label_studio_ml/model.py:291](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/model.py#L291) (+30) |
| L14 | `GET /storage-data/uploaded/` | label_studio_sdk | [label_studio/data_import/urls.py:25](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/data_import/urls.py#L25) | [label_studio_ml/model.py:291](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/model.py#L291) (+30) |
| L15 | `GET /tasks/{task_id}/presign/` | label_studio_sdk | [label_studio/io_storages/urls.py:205](https://github.com/HumanSignal/label-studio/blob/e638bb569a20d1361b6ce6f719d06f87747e94e1/label_studio/io_storages/urls.py#L205) | [label_studio_ml/model.py:291](https://github.com/HumanSignal/label-studio-ml-backend/blob/a13c5fb6e7766c6ce9007c0c77d44d17239ffd42/label_studio_ml/model.py#L291) (+29) |

## Score (frozen finder)

`python -m atlas_bridge links label-studio=… label-studio-ml-backend=… --alias ml=label-studio-ml-backend --scip-dir scip`
(the alias is the name Label Studio uses for the other service: the `MLBackend` model, `/api/ml`), scored with
`eval/score.py`:

| | Sent by the caller's own code | Sent by the SDK | Total |
| --- | --- | --- | --- |
| Production links found | **3 / 4** | 0 / 11 | 3 / 15 |
| False links | 0 | 0 | 0 |

All three found links are confirmed by the SCIP index. The finder also extracted the six requests Label Studio
sends to routes the ML server does not declare (`/train`, `/versions`, `/validate`, `/duplicate_model`, `/delete`,
`/job_status`) and reported them as unmatched, which is what the key says about them.

### Why the rest was missed

1. **The SDK links (11).** The finder links a request to a route when the request is in one of the repositories it
   reads. Here the ML backend calls `get_local_path(...)`, `ls.tasks.get(...)` or `ls.predictions.create(...)`, and the
   HTTP request is built inside `label_studio_sdk`. Finding these needs a link through a library: read the SDK too,
   find the request each SDK method sends, and attach it to the caller's call site, which is a call-graph step
   (a SCIP index built with the SDK installed names the SDK symbol each call resolves to).
2. **`GET /health` (L01).** `MLApi.health` calls the wrapper `self._request(HEALTH_URL, method='GET')`. The wrapper's
   default is `method='POST'`, and the finder forwarded the path but not the `method` keyword, so it looked for
   `POST /health`, which the ML server does not serve. A finder bug, not an unknown idiom.
3. **A mislabelled call (no score effect).** Two calls in the `web/` frontend to Label Studio's own `/api/ml` endpoint
   were given the ML backend as their target because of the `ml` alias. They matched no route, so they are unmatched
   rather than false links, but the alias should not override a relative path the caller's own repository serves.

### After the fix

The `/health` miss had two causes, both fixed after the frozen run: `self.get(url=url, *args, **kwargs)` was read as
`mapping.get(key, default)` (the `*args, **kwargs` counted as two arguments), and a request inside
`if method == 'POST': ... else: ...` was forwarded to every caller instead of only the callers whose arguments take
that branch. Scores after the fix (the frozen numbers above are unchanged):

| | Label Studio | Open edX | Sentry | Mozilla |
| --- | --- | --- | --- | --- |
| Production links | 4 / 15 (4 / 4 sent by the services' own code) | 68 / 71 | 20 / 20 | 0 / 41 |
| False links | 0 | 0 | 0 | 0 |

`/health` is reported as ambiguous: two routes in the ML backend repository serve it (the shared server and an
example's own app), and the finder lists both.

### What this says

Where the request is in the code being read, the finder found 3 of 4 with no false links, on a repository pair it
had never seen. The larger gap here is structural: services often talk to each other through a client library that
lives in a third repository, and a finder that only looks for HTTP calls in the two services cannot see those
links. Reading the client library as a third repository, and following calls into it, is the general fix.
