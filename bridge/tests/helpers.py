import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.dirname(os.path.dirname(HERE))
FIXTURES = os.path.join(HERE, 'fixtures')
GOLDEN = os.path.join(ATLAS, 'test', 'fixtures', 'graphify-shop.json')


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def node(id, label, src, line=None, community=0, **extra):
    n = {
        'id': id,
        'label': label,
        'source_file': src,
        'file_type': 'code',
        'community': community,
        'community_name': f'c{community}',
    }
    if line:
        n['source_location'] = f'L{line}'
    return {**n, **extra}


def edge(a, b, relation='calls', confidence='EXTRACTED'):
    return {'source': a, 'target': b, 'relation': relation, 'confidence': confidence}


# A small Graphify graph: two files in two communities, an external module and a comment node.
GRAPH = {
    'graph': {'graphify_version': '0.9.101'},
    'nodes': [
        node('app', 'app.py', 'app.py', 1),
        node('app_main', 'main()', 'app.py', 3, _callable=True),
        node('app_server', 'Server', 'app.py', 9, _callable=True, _callable_class=True),
        node('db', 'db.py', 'lib/db.py', 1, community=1),
        node('db_query', 'query()', 'lib/db.py', 2, community=1, _callable=True),
        node('db_url', 'URL', 'lib/db.py', 1, community=1),
        node('json', 'json', '', file_type='concept', external=True),
        node('why', 'reason', 'app.py', 3, file_type='rationale'),
    ],
    'links': [
        edge('app', 'app_main', 'contains'),
        edge('app_main', 'db_query'),
        edge('app_main', 'db_query', confidence='INFERRED'),
        edge('app_server', 'db_url', confidence='INFERRED'),
        edge('app', 'db', 'imports_from'),
        edge('app', 'json', 'imports'),
        edge('why', 'app_main', 'rationale_for'),
    ],
}
