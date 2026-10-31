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

On `meta`:

| field | meaning |
| --- | --- |
| `commit` | the commit the graph was built from; shown with summaries and source |
| `docSource` | where `doc` came from: `"comment"` (doc comments), `"ai"` (generated), `"simulated"` (demo). Shown under every summary |
| `sourceBundle` | id of a `<script type="application/json">` holding `{ commit, files: { path: text } }`. Prototype only: stands in for fetching lines live from GitHub |
| `label`, `title`, `source` | scale-button name, title, and the "Indexed with ..." line in the Key |

## Producing a spec

- From code: `tools/index-self/index_self.py` shows how to build one with tree-sitter and SCIP (it indexes Atlas
  itself; adapt `layer()` and the page-specific parts for your repository).
- From a service catalogue, OpenAPI files or tracing data: map systems to repos, bounded contexts to domains,
  deployables to services, operations or topics to leaves, and observed or declared calls to edges.
