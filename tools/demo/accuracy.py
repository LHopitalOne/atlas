"""The accuracy block a demo map shows (meta.accuracy, docs/GRAPH_SPEC.md), from eval/score.py's output and notes.

Usage: python accuracy.py score.txt notes.json [kafka-score.json] > accuracy.json
score.txt ends with eval/score.py's `summary: {...}` line; notes.json holds the text that goes with the numbers
(how the key was built, what was missed, and `key`, the key's path in this repository, which becomes a link
under $KEY_BASE, by default the Atlas repository on GitHub). kafka-score.json, eval/tiny/score.py --json on the Kafka
links against a Kafka key, adds a sentence on how the Kafka links on the map scored.
"""

import json
import os
import sys

SUMMARY = 'summary: '
KEY_BASE = os.environ.get('KEY_BASE', 'https://github.com/LHopitalOne/atlas/blob/master/')


def ratio(text):
    found, of = text.split('/')
    return int(found), int(of)


def kafka_note(path):
    with open(path, encoding='utf-8') as f:
        s = json.load(f)['summary']
    found, of = ratio(s['recall'])
    return (
        f' Kafka topics are on the map too, scored on a second key built the same way: {found} of {of} found, '
        f'{s["false_links"]} false. Producers are read from the code; their consumers, wired in registries and YAML, '
        'are inferred from where another repository names the topic.'
    )


def main(score_path, notes_path, kafka_path=None):
    with open(score_path, encoding='utf-8') as f:
        line = next(x for x in reversed(f.read().splitlines()) if x.startswith(SUMMARY))
    s = json.loads(line[len(SUMMARY):])
    found, of = ratio(s['prod_recall'])
    with open(notes_path, encoding='utf-8') as f:
        notes = json.load(f)
    out = {'found': found, 'of': of, 'falseLinks': s['false_links'], 'scip': ratio(s['prod_confirmed_by_scip'])[0]}
    out.update(notes)
    if kafka_path:
        out['how'] = out.get('how', '') + kafka_note(kafka_path)
    if out.get('key') and not out['key'].startswith('http'):
        out['key'] = KEY_BASE + out['key']
    json.dump(out, sys.stdout, indent=1)


if __name__ == '__main__':
    main(*sys.argv[1:4])
