# Graph spec

The JSON format Atlas reads for real graphs: the embedded "Self" graph, `Atlas.loadGraph(spec)`, and
`node scripts/build.mjs --graph=file.json`. Validated by `validateSpec()` in `src/model/spec.js`.

```json
{
  "meta": {
    "label": "Shop",
    "title": "Shop services",
    "source": "Indexed with my-indexer 1.2",
    "status": ["Matched", "Ambiguous", "Unmatched", "Inferred"],
    "kind":   ["Service", "Endpoint", "Event", "Module"],
    "commit": "a1b2c3d",
    "docSource": "ai"
  },
  "repos": [
    { "name": "web", "domains": [
      { "name": "checkout", "services": [
        { "name": "cart_api", "loc": "services/cart/index.ts:1", "end": 120,
          "doc": "Owns shopping carts: adds, removes and prices items.",
          "sig": "export function createCartApi(db, pricing)",
          "leaves": [
            { "name": "POST /cart", "kind": 1, "loc": "services/cart/routes.ts:14", "end": 31,
              "doc": "Adds an item to the caller's cart.", "sig": "POST /cart { sku, qty } -> Cart" }
        ] },
        { "name": "pay_api" }
      ] }
    ] },
    { "name": "core", "domains": [ { "name": "billing", "services": [ { "name": "ledger" } ] } ] }
  ],
  "edges": [ [3, 1, 0], [1, 2, 1] ]
}
```

## Hierarchy

`repos > domains > services > leaves`. Every repo needs at least one domain; every domain at least one service.
Leaves are optional. On the map, repos and domains are territories, services are discs, leaves are dots around them.

## Node ids (used by `edges`)

Ids are implicit, by order of appearance:

1. **Services first**, `0 .. S-1`, walking repos, then domains, then services in the order given.
2. **Then leaves**, `S .. N-1`, walking services in that same order and each service's leaves in order.

In the example: `cart_api=0, pay_api=1, ledger=2`, then the leaf `POST /cart=3`.

## Edges

`[source, target, status]`: source depends on, calls or uses target. Either end may be a service or a leaf.

| status | default label | meaning on the map |
| --- | --- | --- |
| 0 | Matched | the link is known to be right (solid, neutral) |
| 1 | Ambiguous | the link exists but its target is uncertain (amber) |
| 2 | Unmatched | the caller expects something nothing provides (red) |
| 3 | Inferred | a guessed link, e.g. by heuristics or an LLM (dashed) |

`meta.status` renames these four for your data; the meanings and colours stay.

## Leaf kinds

`kind` is 1, 2 or 3, drawn as circle, diamond and square. `meta.kind[0]` names services and `meta.kind[1..3]` name
the three leaf kinds (for example `["Service", "Endpoint", "Event", "Module"]`).

## Optional fields

On services and leaves:

| field | shown as |
| --- | --- |
| `doc` | "What it does": one or two plain sentences at the top of the inspector, also used by search by meaning |
| `sig` | the signature under the summary (name and parameters, or an endpoint's request and response) |
| `loc` | location, such as `"path/file.ts:42"`; enables "View source" when the page has the file |
| `end` | last line of the definition, so the source view can mark the whole definition |
| `tags` | services only: a few words shown as badges under `doc` (the bridge's `--enrich` writes the file's role first, then its domain) |

On `meta`:

| field | meaning |
| --- | --- |
| `commit` | the commit the graph was built from; shown with summaries and source |
| `docSource` | where `doc` came from: `"comment"` (doc comments), `"ai"` (generated), `"simulated"` (demo). Shown under every summary |
| `docModel` | with `"ai"`: the model that wrote the summaries (e.g. `meta/muse-ember`), named under every summary |
| `sourceBundle` | id of a `<script type="application/json">` holding `{ commit, files: { path: text } }`. Prototype only: stands in for fetching lines live from GitHub |
| `label`, `title`, `source` | scale-button name, title, and the "Indexed with ..." line in the Key |

## HTTP links between repositories (optional)

A spec can carry the proof of every HTTP request one repository sends to a route another serves. The bridge writes
this with `atlas_bridge spec ... --links links.json --repo name=folder --accuracy accuracy.json`. Atlas then draws
each link as an arc from the function that sends the request to the endpoint that serves it, at every zoom, and
clicking one shows its proof.

On each repo, `url` (its web address, e.g. `https://github.com/getsentry/relay`) and `commit` (the commit the map
was built from) turn every cited line into a link to that line at that commit.

Endpoints are leaves (usually `kind` 2, named `"POST /orders"`) on the file that declares the route. Each link is
also an edge, so routing, impact and search see it.

```json
"links": [
  { "from": 12, "to": 40, "method": "POST", "path": "/orders", "proof": "scip",
    "reason": "named target, one route fits",
    "call":  { "repo": 1, "file": "src/api.js", "line": 5, "function": "placeOrder",
               "start": 3, "code": ["…", "…", "  const res = await fetch(`${BASE}/orders`, …);", "…"] },
    "route": { "repo": 0, "file": "app/main.py", "line": 10, "handler": "post_order", "framework": "fastapi",
               "methods": ["POST"], "start": 8, "code": ["…"] },
    "checks": [ { "at": "src/api.js:5", "name": "BASE", "means": "src/api.js:2-2", "verdict": "confirmed" } ] }
],
"unmatched": [
  { "from": 14, "method": "GET", "path": "/users/{id}", "target": -1, "reason": "no route fits",
    "call": { "repo": 1, "file": "src/api.js", "line": 14, "function": "loadUser" } }
]
```

| field | meaning |
| --- | --- |
| `from`, `to` | node ids: the function (or file) that sends the request, and the endpoint leaf that serves it |
| `method`, `path` | the request as the caller sends it, and the route's path |
| `proof` | `scip` (every name it rests on resolves, in a SCIP index, to the assumed definition), `syntax` (the method and path are written at the call site: nothing to resolve), `matched` (read from code, names unchecked), `inferred` (fits only under an assumption, such as a base URL prefix), `judged` (Jev chose it among the routes the code left open), `read` (the extractors missed it; a language model found it in the file and the code checked the claim before matching it), `ambiguous`, `contradicted`, or `outside` |
| `call`, `route` | the two cited sites: `repo` is an index into `repos`; `start` and `code` are the lines shown (optional) |
| `checks` | what SCIP said of each name the link rests on |
| `unmatched` | requests no route was found for: listed in the links panel, not drawn |

`meta.accuracy` says how the links scored on an answer key built without the tool, and is shown with them:
`{ "found": 20, "of": 20, "falseLinks": 0, "scip": 17, "how": "…", "missed": "…", "key": "https://…" }`
(production links found, links in the key, links drawn that the key says are wrong, found links SCIP confirmed, and
plain text on how the key was built, what was missed, and where the key is). Without it the panel says the links
are unmeasured.

## Producing a spec

- From code: `tools/index-self/index_self.py` shows how to build one with tree-sitter and SCIP (it indexes Atlas
  itself; adapt `layer()` and the page-specific parts for your repository).
- From a service catalogue, OpenAPI files or tracing data: map systems to repos, bounded contexts to domains,
  deployables to services, operations or topics to leaves, and observed or declared calls to edges.
