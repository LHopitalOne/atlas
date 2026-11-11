"""Draw fixed samples for the SCIP audit: edges from four buckets (shuffled, buckets hidden) and functions for recall."""
import hashlib, json, os, sys
from atlas_bridge.adapters.graphify import GraphifyReader
from atlas_bridge.adapters.scip import ScipIndex, ScipReferences
from atlas_bridge.cli.inputs import ScipInput
from atlas_bridge.core.model import CodeGraph, Kind, Status
from atlas_bridge.usecases.scipedges import ScipEdges

S = sys.argv[1]
M = '/Users/alexaramyan/personal/dev/codegraph/atlas-demo-ready/.demo-work/mirror'
R = '/Users/alexaramyan/personal/dev/codegraph/demo-repos'
SETS = {
    'sentry': {r: f'{R}/{r}' for r in ('sentry', 'relay', 'snuba', 'symbolicator')},
    'openedx': {r: f'{R}/openedx/{r}' for r in ('openedx-platform', 'course-discovery', 'credentials', 'frontend-app-learning')},
}
PER_BUCKET, FUNCS = 25, 15  # per project set
h = lambda s: hashlib.sha1(s.encode()).hexdigest()
edges_out, key, funcs_out, fkey, SIZES = [], {}, [], {}, {}
for name, roots in SETS.items():
    g = CodeGraph(); rd = GraphifyReader(g)
    for repo in roots:
        rd.read(json.load(open(f'{M}/{repo}/graphify-out/graph.json')), repo)
    before = dict(g.links)
    idx = {}
    for i in ScipInput.in_folder(f'{S}/scip-{name}'):
        idx.setdefault(i.name, []).append(ScipIndex.read(i.path))
    ScipEdges(ScipReferences(idx)).add(g)
    sym = {(f.repo, f.path, s.id): s for f in g.files.values() for s in f.symbols}
    def node(ref):
        if ref.symbol is None:
            return {'repo': ref.repo, 'file': ref.path, 'name': '(module level of the file)', 'line': 0, 'kind': 'file'}
        s = sym[(ref.repo, ref.path, ref.symbol)]
        return {'repo': ref.repo, 'file': ref.path, 'name': ScipEdges.plain(s.name), 'line': s.line, 'kind': s.kind.name.lower()}
    buckets = {
        'graphify_extracted': [e for e, st in before.items() if st == Status.MATCHED],
        'graphify_guess_seen_by_scip': [e for e, st in before.items() if st != Status.MATCHED and e in g.checked],
        'graphify_guess_not_seen': [e for e, st in before.items() if st != Status.MATCHED and e not in g.checked],
        'scip_added': [e for e in g.links if e not in before],
    }
    SIZES[name] = {b: len([e for e in es if e[0].repo in roots and e[1].repo in roots]) for b, es in buckets.items()}
    for b, es in buckets.items():
        es = [e for e in es if e[0].repo in roots and e[1].repo in roots]
        for a, t in sorted(es, key=lambda e: h(f'{e[0]}|{e[1]}'))[:PER_BUCKET]:
            eid = h(f'{name}|{a}|{t}')[:10]
            edges_out.append({'id': eid, 'root': roots[a.repo], 'target_root': roots[t.repo], 'source': node(a), 'target': node(t)})
            key[eid] = {'set': name, 'bucket': b, 'in_graphify': (a, t) in before, 'scip': (a, t) in g.checked}
    # recall: Python functions with a body, outgoing edges in each graph
    fns = [(f, s) for f in g.files.values() for s in f.symbols if s.kind == Kind.FUNCTION and f.path.endswith('.py')]
    for f, s in sorted(fns, key=lambda p: h(f'{p[0].repo}|{p[0].path}|{p[1].id}'))[:FUNCS]:
        ref = (f.repo, f.path, s.id)
        fid = h(f'{name}|{ref}')[:10]
        funcs_out.append({'id': fid, 'root': roots[f.repo], 'repo': f.repo, 'file': f.path, 'name': ScipEdges.plain(s.name), 'line': s.line})
        out = lambda links: sorted({(t.path, ScipEdges.plain(sym[(t.repo, t.path, t.symbol)].name) if t.symbol else '') for (a, t) in links if (a.repo, a.path, a.symbol) == ref})
        fkey[fid] = {'set': name, 'graphify': out(before), 'with_scip': out(g.links)}
json.dump(SIZES, open(f"{S}/audit/sizes.json","w"), indent=1); print(SIZES); sys.exit()
os.makedirs(f'{S}/audit', exist_ok=True)
json.dump(edges_out, open(f'{S}/audit/edges.json', 'w'), indent=1)
json.dump(key, open(f'{S}/audit/edges-key.json', 'w'), indent=1)
json.dump(funcs_out, open(f'{S}/audit/functions.json', 'w'), indent=1)
json.dump(fkey, open(f'{S}/audit/functions-key.json', 'w'), indent=1)
print(len(edges_out), 'edges', len(funcs_out), 'functions')
