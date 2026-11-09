# Third test: HTTP links between Mozilla Add-ons services

The second held-out test, run after the fixes made on [Open edX](../openedx/README.md). The finder was frozen
before the key was built (a snapshot of commit `857f312` plus the uncommitted Open edX fixes, content hash
`2760c9bbc3d7`) and run once; the score below is that run, unchanged.

| Repository | Commit |
| --- | --- |
| addons-server (Django, DRF) | [65a56ea](https://github.com/mozilla/addons-server/tree/65a56ea495b315b9887c7f7734e408d6c444b537) |
| addons-frontend (React) | [b2ed6ce](https://github.com/mozilla/addons-frontend/tree/b2ed6ceaa35c85c86109766e345bf25223c71a08) |

## How it was made

As for Open edX: one agent per repository listed every request it sends to the other and traced it to the serving
route (DRF routers, nested routers, `@action`s, the versioned API mounts), without seeing the finder. A second agent
tried to refute each link; 41 of 44 held, and the 3 it rejected are excluded by the same rules as before (a helper
nothing calls, a browser navigation, a file URL Firefox fetches). A script checked every cited line exists.
addons-server sends no request to addons-frontend, so every link is frontend -> server. A machine-built and
machine-checked key, not a human review.

## Links (41, all production)

| Id | Request | Served by | Called from |
| --- | --- | --- | --- |
| M01 | `POST /api/v5/abuse/report/addon/` | [src/olympia/abuse/api_urls.py:15](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/abuse/api_urls.py#L15) | [src/amo/api/abuse.js:72](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/abuse.js#L72) (+1) |
| M02 | `POST /api/v5/abuse/report/collection/` | [src/olympia/abuse/api_urls.py:16](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/abuse/api_urls.py#L16) | [src/amo/api/abuse.js:256](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/abuse.js#L256) (+1) |
| M03 | `POST /api/v5/abuse/report/rating/` | [src/olympia/abuse/api_urls.py:19](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/abuse/api_urls.py#L19) | [src/amo/api/abuse.js:196](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/abuse.js#L196) (+1) |
| M04 | `POST /api/v5/abuse/report/user/` | [src/olympia/abuse/api_urls.py:20](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/abuse/api_urls.py#L20) | [src/amo/api/abuse.js:136](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/abuse.js#L136) (+1) |
| M05 | `DELETE /api/v5/accounts/account/{pk}/` | [src/olympia/accounts/urls.py:12](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L12) | [src/amo/api/users.js:155](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L155) (+1) |
| M06 | `GET /api/v5/accounts/account/{pk}/` | [src/olympia/accounts/urls.py:12](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L12) | [src/amo/api/users.js:88](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L88) (+1) |
| M07 | `PATCH /api/v5/accounts/account/{pk}/` | [src/olympia/accounts/urls.py:12](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L12) | [src/amo/api/users.js:73](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L73) (+1) |
| M08 | `DELETE /api/v5/accounts/account/{pk}/picture/` | [src/olympia/accounts/views.py:552](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/views.py#L552) | [src/amo/api/users.js:139](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L139) (+1) |
| M09 | `GET /api/v5/accounts/account/{user_pk}/collections/` | [src/olympia/accounts/urls.py:15](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L15) | [src/amo/api/collections.js:103](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L103) (+1) |
| M10 | `POST /api/v5/accounts/account/{user_pk}/collections/` | [src/olympia/accounts/urls.py:15](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L15) | [src/amo/api/collections.js:208](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L208) (+1) |
| M11 | `GET /api/v5/accounts/account/{user_pk}/collections/{collection_slug}/addons/` | [src/olympia/accounts/urls.py:17](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L17) | [src/amo/api/collections.js:55](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L55) (+3) |
| M12 | `POST /api/v5/accounts/account/{user_pk}/collections/{collection_slug}/addons/` | [src/olympia/accounts/urls.py:17](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L17) | [src/amo/api/collections.js:297](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L297) (+2) |
| M13 | `DELETE /api/v5/accounts/account/{user_pk}/collections/{collection_slug}/addons/{addon}/` | [src/olympia/accounts/urls.py:17](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L17) | [src/amo/api/collections.js:367](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L367) (+1) |
| M14 | `PATCH /api/v5/accounts/account/{user_pk}/collections/{collection_slug}/addons/{addon}/` | [src/olympia/accounts/urls.py:17](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L17) | [src/amo/api/collections.js:305](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L305) (+1) |
| M15 | `DELETE /api/v5/accounts/account/{user_pk}/collections/{slug}/` | [src/olympia/accounts/urls.py:15](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L15) | [src/amo/api/collections.js:390](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L390) (+1) |
| M16 | `GET /api/v5/accounts/account/{user_pk}/collections/{slug}/` | [src/olympia/accounts/urls.py:15](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L15) | [src/amo/api/collections.js:29](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L29) (+1) |
| M17 | `PATCH /api/v5/accounts/account/{user_pk}/collections/{slug}/` | [src/olympia/accounts/urls.py:15](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L15) | [src/amo/api/collections.js:208](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/collections.js#L208) (+1) |
| M18 | `GET /api/v5/accounts/account/{user_pk}/notifications/` | [src/olympia/accounts/urls.py:20](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L20) | [src/amo/api/users.js:102](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L102) (+1) |
| M19 | `POST /api/v5/accounts/account/{user_pk}/notifications/` | [src/olympia/accounts/urls.py:20](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L20) | [src/amo/api/users.js:124](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L124) (+1) |
| M20 | `GET /api/v5/accounts/profile/` | [src/olympia/accounts/urls.py:30](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L30) | [src/amo/api/users.js:34](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L34) (+1) |
| M21 | `DELETE /api/v5/accounts/session/` | [src/olympia/accounts/urls.py:28](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L28) | [src/amo/api/index.js:294](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/index.js#L294) (+1) |
| M22 | `POST /api/v5/accounts/unsubscribe/` | [src/olympia/accounts/urls.py:37](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/accounts/urls.py#L37) | [src/amo/api/users.js:177](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/users.js#L177) (+1) |
| M23 | `GET /api/v5/addons/addon/{addon_pk}/versions/` | [src/olympia/addons/api_urls.py:33](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L33) | [src/amo/api/versions.js:52](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/versions.js#L52) (+1) |
| M24 | `GET /api/v5/addons/addon/{addon_pk}/versions/{pk}/` | [src/olympia/addons/api_urls.py:33](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L33) | [src/amo/api/versions.js:29](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/versions.js#L29) (+1) |
| M25 | `GET /api/v5/addons/addon/{pk}/` | [src/olympia/addons/api_urls.py:29](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L29) | [src/amo/api/index.js:252](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/index.js#L252) (+2) |
| M26 | `GET /api/v5/addons/addon/{pk}/eula_policy/` | [src/olympia/addons/views.py:389](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/views.py#L389) | [src/amo/api/addonInfo.js:27](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/addonInfo.js#L27) (+1) |
| M27 | `GET /api/v5/addons/autocomplete/` | [src/olympia/addons/api_urls.py:52](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L52) | [src/amo/api/index.js:320](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/index.js#L320) (+1) |
| M28 | `GET /api/v5/addons/categories/` | [src/olympia/addons/api_urls.py:57](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L57) | [src/amo/api/categories.js:12](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/categories.js#L12) (+1) |
| M29 | `GET /api/v5/addons/language-tools/` | [src/olympia/addons/api_urls.py:59](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L59) | [src/amo/api/languageTools.js:15](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/languageTools.js#L15) (+1) |
| M30 | `GET /api/v5/addons/recommendations/` | [src/olympia/addons/api_urls.py:67](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L67) | [src/amo/api/recommendations.js:28](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/recommendations.js#L28) (+1) |
| M31 | `GET /api/v5/addons/search/` | [src/olympia/addons/api_urls.py:56](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/addons/api_urls.py#L56) | [src/amo/api/search.js:67](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/search.js#L67) (+4) |
| M32 | `GET /api/v5/blocklist/block/{pk}/` | [src/olympia/blocklist/urls.py:9](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/blocklist/urls.py#L9) | [src/amo/api/blocks.js:14](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/blocks.js#L14) (+1) |
| M33 | `GET /api/v5/ratings/rating/` | [src/olympia/ratings/api_urls.py:10](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/api_urls.py#L10) | [src/amo/api/reviews.js:169](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L169) (+4) |
| M34 | `POST /api/v5/ratings/rating/` | [src/olympia/ratings/api_urls.py:10](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/api_urls.py#L10) | [src/amo/api/reviews.js:80](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L80) (+1) |
| M35 | `DELETE /api/v5/ratings/rating/{pk}/` | [src/olympia/ratings/api_urls.py:10](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/api_urls.py#L10) | [src/amo/api/reviews.js:269](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L269) (+1) |
| M36 | `GET /api/v5/ratings/rating/{pk}/` | [src/olympia/ratings/api_urls.py:10](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/api_urls.py#L10) | [src/amo/api/reviews.js:292](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L292) (+1) |
| M37 | `PATCH /api/v5/ratings/rating/{pk}/` | [src/olympia/ratings/api_urls.py:10](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/api_urls.py#L10) | [src/amo/api/reviews.js:83](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L83) (+1) |
| M38 | `POST /api/v5/ratings/rating/{pk}/flag/` | [src/olympia/ratings/views.py:445](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/views.py#L445) | [src/amo/api/reviews.js:244](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L244) (+1) |
| M39 | `POST /api/v5/ratings/rating/{pk}/reply/` | [src/olympia/ratings/views.py:426](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/ratings/views.py#L426) | [src/amo/api/reviews.js:121](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/reviews.js#L121) (+1) |
| M40 | `GET /api/v5/shelves/` | [src/olympia/shelves/urls.py:9](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/shelves/urls.py#L9) | [src/amo/api/homeShelves.js:13](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/homeShelves.js#L13) (+1) |
| M41 | `GET /api/v5/site/` | [src/olympia/amo/urls.py:24](https://github.com/mozilla/addons-server/blob/65a56ea495b315b9887c7f7734e408d6c444b537/src/olympia/amo/urls.py#L24) | [src/amo/api/site.js:17](https://github.com/mozilla/addons-frontend/blob/b2ed6ceaa35c85c86109766e345bf25223c71a08/src/amo/api/site.js#L17) (+2) |

## Score (frozen finder)

`python -m atlas_bridge links addons-server=… addons-frontend=… --alias api=addons-server --scip-dir scip`
(the alias is the name the frontend uses for the server: `callApi`, `apiHost`), scored with `eval/score.py`:

| | Mozilla Add-ons | Open edX (after fixes) | Sentry |
| --- | --- | --- | --- |
| Production links | **0 / 41** | 61 / 71 | 20 / 20 |
| False links | 0 | 0 | 0 |

### Why nothing was found

1. **Requests through a wrapper that takes an object.** 39 of the 41 links are only sent through `callApi({ endpoint:
   'ratings/rating', method, ... })`. The path is a property of an object argument, and `callApi` turns it into the URL
   through `url.parse(endpoint)`, a conditional prefix (`${apiPath}${slash}${adjustedEndpoint}`) and a reassigned
   variable before `fetch`. The finder follows wrapper *parameters* to their callers, not object properties, so the
   `fetch` inside `callApi` reads as a URL with nothing known and the requests are never extracted.
2. **The API's routes are built by a function.** v3, v4 and v5 are mounted with
   `*get_versioned_api_routes('v5', v5_api_urls)`, which builds `rf'^{version}/'` from its argument and a list it
   appends to before returning it. The finder follows list-building functions only when they return a list literal,
   so none of the `/api/v5/` routes exists for it (3 `/api/` routes out of the API's hundreds). Even perfect request
   extraction would have found nothing to match.
3. **The two requests outside `callApi`** (`fetch` in `src/blog-utils/index.js` and `src/amo/utils/server.js`) are
   absolute URLs to `https://addons.mozilla.org`, and no configuration the finder reads ties that host to
   addons-server (it is in the frontend's `config/default.js`, a JS object, not a settings module, `.env` or compose
   file).

### What this says

The Open edX fixes were real rules (they changed nothing here for the worse: no false links), but each project
builds URLs and routes in its own ways, and the finder still knows a fixed list of them. Mozilla's two idioms, a
request wrapper that takes an options object and a route list built by a function, are both common. The general fix
for the first is to forward object properties through wrappers as it forwards parameters; for the second, to
evaluate list-building functions with their arguments (locals, `append`, f-strings) as it already does for URL
helpers.
