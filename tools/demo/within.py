"""Keep only the links inside one repository from a `links --within` run (a frontend calling its own API).

Usage: python within.py links.json > within.json
A run on one repository also lists its requests to other services as unmatched; those already appear, with their
targets, in the run across all the repositories, so they are dropped here.
"""

import json
import sys


def main(path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    data['links'] = [lk for lk in data['links'] if lk.get('route') and lk['caller'] == lk.get('target')]
    json.dump(data, sys.stdout, indent=1)


if __name__ == '__main__':
    main(sys.argv[1])
