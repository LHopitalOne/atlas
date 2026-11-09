#!/usr/bin/env python3
"""Score a links.json against a tiny app's TRUTH.json, for every protocol.

A TRUTH link is found when the finder reports a link with the same caller and target services whose receiving end is
the TRUTH link's: the same file within 2 lines of its `receive` line, or (for HTTP-like protocols) the same
normalised channel with a compatible operation. Finder links that match no TRUTH link are false links, unless their
call site is listed under the app's not_links.

Usage: python3 eval/tiny/score.py TRUTH.json links.json [--json]
"""

import json
import re
import sys

PARAMETER = re.compile(r'\{[^}]*\}')  # '{id}' and '{*rest}' alike: parameter names differ between the two sides
HTTP_LIKE = {'http', 'websocket', 'graphql'}


def norm(path):
    p = PARAMETER.sub('{}', (path or '').lower()).rstrip('/')
    return p or '/'


def operation_fits(truth_op, found_methods, found_method):
    ops = {m.upper() for m in found_methods or []} | {(found_method or '').upper()}
    return not truth_op or 'ANY' in ops or truth_op.upper() in ops


def channel(protocol, name):
    """A channel as both sides can be compared: an HTTP path normalised; a gRPC 'Service/Method' without its package
    (a servicer names only the service); a topic, queue or port as its bare name."""
    name = re.sub(r'^(tcp|udp):', '', (name or '').strip())
    if protocol in HTTP_LIKE:
        return norm(name)
    name = name.strip('/').lower()
    if protocol == 'grpc' and '/' in name:
        service, method = name.rsplit('/', 1)
        return f'{service.rsplit(".", 1)[-1]}/{method}'
    return name


def same_link(t, f):
    r = f.get('route')
    if not r or t['caller'] != f['caller'] or t['target'] != f['target']:
        return False
    if r.get('protocol', 'http') != t['protocol'] and not (t['protocol'] == 'graphql' and r.get('protocol') == 'http'):
        return False
    rec = t['receive']
    if rec['file'] == r['file'] and abs(rec['line'] - r['line']) <= 2:
        return True
    if channel(t['protocol'], t['channel']) == channel(t['protocol'], r['path']):
        return t['protocol'] not in HTTP_LIKE or operation_fits(t.get('operation'), r.get('methods'), f['call'].get('method'))
    return False


def excused(truth, f):
    """A finder link whose call site the app lists as not a link (self-call, external, test only)."""
    at = f'{f["caller"]}:{f["call"]["file"]}:'
    return any(n.get('where', '').startswith(at) for n in truth.get('not_links', []))


def score(truth, found):
    links = [f for f in found['links'] if f.get('route')]
    rows, matched = [], set()
    for t in truth['links']:
        hits = [i for i, f in enumerate(links) if same_link(t, f)]
        matched.update(hits)
        rows.append({'id': t['id'], 'protocol': t['protocol'], 'link': f'{t["caller"]} -> {t["target"]} '
                     f'{t["operation"]} {t["channel"]}', 'found': bool(hits), 'idiom': t.get('idiom', ''),
                     'status': sorted({links[i]['status'] for i in hits})})
    false = [f for i, f in enumerate(links) if i not in matched and not excused(truth, f)]
    by_protocol = {}
    for r in rows:
        got, total = by_protocol.get(r['protocol'], (0, 0))
        by_protocol[r['protocol']] = (got + r['found'], total + 1)
    return {
        'project': truth['project'],
        'rows': rows,
        'false': [f'{f["caller"]} -> {f["target"]} {f["call"]["method"]} {f["call"]["path"]} => '
                  f'{f["route"]["path"]} at {f["call"]["file"]}:{f["call"]["line"]}' for f in false],
        'summary': {
            'recall': f'{sum(r["found"] for r in rows)}/{len(rows)}',
            'by_protocol': {p: f'{g}/{t}' for p, (g, t) in sorted(by_protocol.items())},
            'false_links': len(false),
        },
    }


def main(argv):
    with open(argv[1], encoding='utf-8') as f:
        truth = json.load(f)
    with open(argv[2], encoding='utf-8') as f:
        found = json.load(f)
    report = score(truth, found)
    if '--json' in argv:
        print(json.dumps(report, indent=1))
        return
    for r in report['rows']:
        print(f'  [{"x" if r["found"] else " "}] {r["id"]} {r["protocol"]:9} {r["link"]}  ({r["idiom"][:70]})')
    for f in report['false']:
        print(f'  FALSE {f}')
    print('summary:', json.dumps(report['summary']))


if __name__ == '__main__':
    main(sys.argv)
