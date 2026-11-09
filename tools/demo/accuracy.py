"""The accuracy block a demo map shows (meta.accuracy, docs/GRAPH_SPEC.md), from eval/score.py's output and notes.

Usage: python accuracy.py score.txt notes.json > accuracy.json
score.txt ends with eval/score.py's `summary: {...}` line; notes.json holds the text that goes with the numbers
(how the key was built, what was missed, and `key`, the key's path in this repository, which becomes a link
under $KEY_BASE, by default the Atlas repository on GitHub).
"""

import json
import os
import sys

SUMMARY = 'summary: '
KEY_BASE = os.environ.get('KEY_BASE', 'https://github.com/LHopitalOne/atlas/blob/master/')


def ratio(text):
    found, of = text.split('/')
    return int(found), int(of)


def main(score_path, notes_path):
    with open(score_path, encoding='utf-8') as f:
        line = next(x for x in reversed(f.read().splitlines()) if x.startswith(SUMMARY))
    s = json.loads(line[len(SUMMARY):])
    found, of = ratio(s['prod_recall'])
    with open(notes_path, encoding='utf-8') as f:
        notes = json.load(f)
    out = {'found': found, 'of': of, 'falseLinks': s['false_links'], 'scip': ratio(s['prod_confirmed_by_scip'])[0]}
    out.update(notes)
    if out.get('key') and not out['key'].startswith('http'):
        out['key'] = KEY_BASE + out['key']
    json.dump(out, sys.stdout, indent=1)


if __name__ == '__main__':
    main(*sys.argv[1:3])
