# gateway: a small marketplace behind an API gateway

Bazaarly, a toy marketplace. The browser app only talks to an Express API gateway, which proxies to two upstream
services and has one hand-written aggregation route. The orders service also calls users directly and an outside
currency API.

## Services

| Service | Folder | Stack | Port |
| --- | --- | --- | --- |
| edge | `edge/` | Express + http-proxy-middleware (TypeScript, tsx) | 43010 |
| spa | `spa/` | Vite + TypeScript, axios instance with `baseURL: '/api'` | (driven from Node) |
| users | `users/` | Rust, axum 0.8 with nested routers | 43020 |
| orders | `orders/` | Python 3.13, Flask with (nested) blueprints, requests | 43030 |

`./run.sh` builds and installs everything, starts users, orders and edge, runs `spa/scripts/drive.ts` (it imports the
real `spa/src/api` module, points the axios instance at the gateway origin, and fetches the third-party URLs found in
`index.html`), then writes every `RECV <link id>` line to `observed.log` and checks it against `TRUTH.json`.
No Docker is used.

## Links (15)

| Protocol | Count | Links |
| --- | --- | --- |
| HTTP through the gateway proxy (spa -> users) | 4 | L01 GET /users, L02 GET /users/{id}, L03 POST /users, L04 GET /users/{id}/wishlist |
| HTTP through the gateway proxy (spa -> orders) | 4 | L05 GET /v1/orders, L06 POST /v1/orders, L07 GET /v1/orders/{order_id}, L08 GET /v1/orders/{order_id}/items |
| HTTP spa -> edge (own route) | 1 | L09 GET /api/dashboard/{userId} |
| HTTP edge -> upstream (fetch) | 2 | L10 GET users /users/{id}, L11 GET orders /v1/orders |
| HTTP orders -> users (requests) | 1 | L12 GET /internal/buyers/{id}/verify |
| Outside hosts | 3 | O01 GET open.er-api.com /v6/latest/USD, O02 GET unpkg.com script, O03 LINK github.com/bazaarly |

For proxied links, `send` lists the spa call site (axios instance + api function) and the edge proxy config lines;
`channel` is the path the upstream sees after `pathRewrite`.

## Idioms tested

- axios instance with a relative `baseURL` (`'/api'`); paths as string literals, template literals, and a module const
  (`ORDERS`) interpolated into template literals; query via axios `params`.
- http-proxy-middleware v3 mounted with `app.use(proxy)` and `pathFilter` (string for users, function for orders);
  `pathRewrite` as an object (`'^/api': ''`) and as a function (`/api/orders` -> `/v1/orders`), so the upstream path
  differs from the browser path in two different ways.
- Hand-written aggregation route on an Express Router mounted at `/api/dashboard`, calling both upstreams with global
  `fetch` through a generic `getJson<T>` helper inside `Promise.all`, with URLs built by `new URL(path, base)` and a
  template literal + `URLSearchParams`.
- axum `Router::nest` at two levels, including a nest prefix with a path capture (`/users` + `/{id}/wishlist` + `/`),
  method-chained `get(..).post(..)` on one route.
- Flask blueprints with `url_prefix`, empty rule `""`, `@bp.get`/`@bp.post` shortcuts, and a nested blueprint
  (`orders_bp.register_blueprint(items_bp)` with a prefix that contains a converter).
- Service-to-service call through a `requests.Session` wrapped in a client class built in the app factory from an env
  var; outside API through a module-level URL constant.
- HTML: `<script src>` from a CDN and `<a href>` to GitHub.

Callers are told apart at the receiver by `X-Forwarded-For` (set by the proxy's `xfwd: true`): users/orders log L02 vs
L10 and L05 vs L11 from the same handlers.
