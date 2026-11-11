"""Score the audit: precision per bucket (and weighted per graph), recall of each graph on the listed real uses."""
import glob, json, os, sys
from collections import defaultdict
S = sys.argv[1]; A = f'{S}/audit'
key = json.load(open(f'{A}/edges-key.json')); sizes = json.load(open(f'{A}/sizes.json'))
verdicts = {}
for p in glob.glob(f'{A}/results/edges*.json'):
    for v in json.load(open(p)): verdicts[v['id']] = v['verdict'].lower()
cnt = defaultdict(lambda: defaultdict(int))
for eid, k in key.items():
    v = verdicts.get(eid, 'missing'); cnt[(k['set'], k['bucket'])][v] += 1; cnt[('all', k['bucket'])][v] += 1
def prec(c): yes, no = c['yes'], c['no']; return yes / (yes + no) if yes + no else float('nan')
print('PRECISION by bucket (yes / (yes+no); unclear apart)')
for (s, b), c in sorted(cnt.items()):
    print(f'  {s:8} {b:28} yes {c["yes"]:3} no {c["no"]:3} unclear {c["unclear"]:3} missing {c["missing"]:2}  precision {prec(c):.0%}')
print('GRAPH precision (bucket precision weighted by bucket size)')
for s in sizes:
    p = {b: prec(cnt[(s, b)]) for b in sizes[s]}
    def weighted(bs):
        n = sum(sizes[s][b] for b in bs); return sum(sizes[s][b] * p[b] for b in bs) / n, n
    g, gn = weighted(['graphify_extracted', 'graphify_guess_seen_by_scip', 'graphify_guess_not_seen'])
    w, wn = weighted(['graphify_extracted', 'graphify_guess_seen_by_scip', 'graphify_guess_not_seen', 'scip_added'])
    print(f'  {s:8} Graphify {gn:,} edges, ~{g:.0%} correct (~{round(g*gn):,} true) | +SCIP {wn:,} edges, ~{w:.0%} correct (~{round(w*wn):,} true)')
fkey = json.load(open(f'{A}/functions-key.json')); funcs = {f['id']: f for f in json.load(open(f'{A}/functions.json'))}
uses = {}
for p in glob.glob(f'{A}/results/functions*.json'):
    for u in json.load(open(p)): uses[u['id']] = u['uses']
tot = defaultdict(lambda: [0, 0, 0])
for fid, us in uses.items():
    k = fkey[fid]
    g = {(f, n) for f, n in k['graphify']}; w = {(f, n) for f, n in k['with_scip']}
    gf = {f for f, n in k['graphify']}; wf = {f for f, n in k['with_scip']}
    for u in us:
        if not u.get('confident', True): continue
        t = (u['file'], u['name'])
        hit = lambda edges, files: t in edges or (u['file'] in files and (u['file'], '') in edges)
        for s in (k['set'], 'all'):
            tot[s][0] += 1; tot[s][1] += t in g; tot[s][2] += t in w
print('RECALL on real uses listed in sampled functions (confident uses, exact target match)')
for s, (n, g, w) in tot.items():
    print(f'  {s:8} {n} uses: Graphify finds {g} ({g/n:.0%}), Graphify+SCIP finds {w} ({w/n:.0%})')
