#!/usr/bin/env python3
"""Run the link finder on every tiny app under a folder and score it against the app's TRUTH.json.

Each service folder is one repository; no aliases are given (a first try, as on code never seen). Links inside one
service (a frontend calling its own backend) are looked for with --within.

A TRUTH.json may name its code's folder with "root" (the development-set keys in eval/devset do); otherwise the
code is the app folder itself.

Usage: python3 eval/tiny/run.py <apps folder> <output folder> [--python /path/to/python] [-- extra links options]
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, '..', '..', 'bridge')
sys.path.insert(0, HERE)
from score import score  # noqa: E402


def run_app(app, python, out, extra):
    with open(os.path.join(app, 'TRUTH.json'), encoding='utf-8') as f:
        truth = json.load(f)
    root = os.path.expanduser(truth.get('root', app))  # a key kept apart from its code names the code's folder
    repos = [f'{name}={os.path.normpath(os.path.join(root, folder))}' for name, folder in truth['services'].items()]
    links = os.path.join(out, f'{truth["project"]}.links.json')
    cmd = [python, '-m', 'atlas_bridge', 'links', *repos, '--within', '-o', links, *extra]
    done = subprocess.run(cmd, cwd=BRIDGE, capture_output=True, text=True)
    if done.returncode != 0:
        return {'project': truth['project'], 'error': (done.stderr or done.stdout)[-500:]}
    with open(links, encoding='utf-8') as f:
        return score(truth, json.load(f))


def main(argv):
    apps, out = os.path.abspath(argv[1]), os.path.abspath(argv[2])
    python = argv[argv.index('--python') + 1] if '--python' in argv else sys.executable
    extra = argv[argv.index('--') + 1 :] if '--' in argv else []
    os.makedirs(out, exist_ok=True)
    reports = []
    for name in sorted(os.listdir(apps)):
        if os.path.isfile(os.path.join(apps, name, 'TRUTH.json')):
            reports.append(run_app(os.path.join(apps, name), python, out, extra))
    totals, false = {}, 0
    for r in reports:
        if 'error' in r:
            print(f'{r["project"]}: ERROR {r["error"]}')
            continue
        print(f'{r["project"]:10} {r["summary"]["recall"]:>6}  false {r["summary"]["false_links"]}  '
              f'{r["summary"]["by_protocol"]}')
        false += r['summary']['false_links']
        for row in r['rows']:
            got, total = totals.get(row['protocol'], (0, 0))
            totals[row['protocol']] = (got + row['found'], total + 1)
    found, total = sum(g for g, _ in totals.values()), sum(t for _, t in totals.values())
    print(f'ALL        {found}/{total}  false {false}  ' + json.dumps({p: f'{g}/{t}' for p, (g, t) in sorted(totals.items())}))
    with open(os.path.join(out, 'report.json'), 'w', encoding='utf-8') as f:
        json.dump(reports, f, indent=1)


if __name__ == '__main__':
    main(sys.argv)
