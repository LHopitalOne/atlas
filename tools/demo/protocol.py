"""Keep only the links of one protocol from a links JSON (atlas_bridge links), for the answer key of that protocol.

Usage: python protocol.py http|kafka|... links.json > links-<protocol>.json
A link's protocol is its route's, or its call's when it reached no route.
"""

import json
import sys


def protocol(link):
    return (link.get('route') or link['call']).get('protocol') or 'http'


def main(wanted, path):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    data['links'] = [lk for lk in data['links'] if protocol(lk) == wanted]
    json.dump(data, sys.stdout, indent=1)


if __name__ == '__main__':
    main(*sys.argv[1:3])
