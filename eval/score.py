#!/usr/bin/env python3
"""Score a links.json (python -m atlas_bridge links) against an answer key (eval/<project>/answer-key.json).

A key link is found when the finder reports a link with the same caller and target repositories whose route is the
same: equal paths (ignoring parameter names and trailing slashes), or the same route file within 3 lines with the same fixed words (a route written as a regex).
Finder links that match no key link are split into those whose call site the key excludes on purpose (tests,
tooling, plumbing) and the rest, which are false links.

Usage: python3 eval/score.py eval/sentry/answer-key.json links.json [--json]
"""

import json
import re
import sys


PARAMETER = re.compile(r'\{[^}]*\}')  # '{name}' or '{*rest}': names differ between a route and the key


def norm(path):
    p = PARAMETER.sub('{}', (path or '').lower()).rstrip('/')
    return p or '/'


def same_route(key, found, paths=frozenset()):
    """paths: the key's normalised paths between the same two repositories. The nearby-line fallback is for a route
    the finder writes differently (a regex): it needs the same fixed words, and does not apply to a found route whose
    path is another key link's."""
    r = found.get('route')
    if not r or key['caller'] != found['caller'] or key['target'] != found['target']:
        return False
    if norm(key['path']) == norm(r['path']):
        return True
    if norm(r['path']) in paths or literals(r['path']) != literals(key['path']):
        return False
    return key['route']['file'] == r['file'] and abs(key['route']['line'] - r['line']) <= 3


def literals(path):
    """The fixed words of a path: a route written as a regex and the same route written with converters share them."""
    return [s for s in norm(path).split('/') if s and '{' not in s]


def excluded_by_key(key, found):
    call = found['call']
    return any(
        e['caller'] == found['caller'] and e['file'] == call['file'] and abs(e['line'] - call['line']) <= 3
        for e in key['excluded']
    )


def score(key, found):
    links = [f for f in found['links'] if f.get('route')]
    report = {
        'scopes': {},
        'false': [],
        'excluded': [],
        'unmatched_calls': sum(1 for f in found['links'] if not f.get('route')),
    }
    matched = set()
    known = {}
    for k in key['links']:
        known.setdefault((k['caller'], k['target']), set()).add(norm(k['path']))
    for scope in sorted({k['scope'] for k in key['links']}):
        rows = []
        for k in (k for k in key['links'] if k['scope'] == scope):
            paths = known.get((k['caller'], k['target']), frozenset())
            hits = [i for i, f in enumerate(links) if same_route(k, f, paths)]
            matched.update(hits)
            statuses = sorted({links[i]['status'] for i in hits})
            verified = sorted({links[i].get('verification', 'unverified') for i in hits})
            rows.append(
                {
                    'id': k['id'],
                    'link': f'{k["caller"]} -> {k["target"]} {k["method"]} {k["path"]}',
                    'found': bool(hits),
                    'status': statuses,
                    'how': k['how_the_path_is_known'],
                    'verification': verified,
                }
            )
        report['scopes'][scope] = rows
    for i, f in enumerate(links):
        if i in matched:
            continue
        row = {
            'link': f'{f["caller"]} -> {f["target"]} {f["call"]["method"]} {f["call"]["path"]} => '
            f'{"|".join(f["route"]["methods"])} {f["route"]["path"]}',
            'status': f['status'],
            'at': f'{f["call"]["file"]}:{f["call"]["line"]}',
        }
        report['excluded' if excluded_by_key(key, f) else 'false'].append(row)
    prod = report['scopes'].get('prod', [])
    tp = sum(r['found'] for r in prod)
    false = len(report['false'])
    report['summary'] = {
        'prod_recall': f'{tp}/{len(prod)}',
        'precision': f'{len(matched)}/{len(matched) + false}' if matched or false else 'n/a',
        'false_links': false,
        'links_to_excluded_calls': len(report['excluded']),
        'prod_confirmed_by_scip': f"{sum('confirmed' in r['verification'] for r in prod)}/{len(prod)}",
    }
    return report


def main(argv):
    with open(argv[1], encoding='utf-8') as f:
        key = json.load(f)
    with open(argv[2], encoding='utf-8') as f:
        found = json.load(f)
    report = score(key, found)
    if '--json' in argv:
        print(json.dumps(report, indent=1))
        return
    for scope, rows in report['scopes'].items():
        hit = sum(r['found'] for r in rows)
        print(f'\n{scope}: {hit}/{len(rows)} found')
        for r in rows:
            mark = 'x' if r['found'] else ' '
            status = ', ' + '/'.join(r['status']) if r['status'] else ''
            scip = ', SCIP ' + '/'.join(r['verification']) if r['verification'] else ''
            print(f'  [{mark}] {r["id"]} {r["link"]}  ({r["how"]}{status}{scip})')
    for name in ('false', 'excluded'):
        title = 'false links' if name == 'false' else 'links from call sites the key excludes (tests, tooling)'
        print(f'\n{title}: {len(report[name])}')
        for r in report[name]:
            print(f'  {r["status"]:9} {r["link"]}  at {r["at"]}')
    print('\nsummary:', json.dumps(report['summary']))


if __name__ == '__main__':
    main(sys.argv)
