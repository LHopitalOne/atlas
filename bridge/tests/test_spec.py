import json
import os
import shutil
import subprocess
import unittest

from atlas_bridge.spec import SpecBuilder

ATLAS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def node(id, label, src, line=None, community=0, **extra):
    n = {'id': id, 'label': label, 'source_file': src, 'file_type': 'code', 'community': community,
         'community_name': f'c{community}'}
    if line: n['source_location'] = f'L{line}'
    return {**n, **extra}


def edge(a, b, relation='calls', confidence='EXTRACTED'):
    return {'source': a, 'target': b, 'relation': relation, 'confidence': confidence}


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


def build(graph=GRAPH, **kw):
    b = SpecBuilder(**kw)
    b.add(graph, 'shop')
    return b.build()


class SpecTest(unittest.TestCase):
    def test_hierarchy(self):
        spec = build()
        self.assertEqual([r['name'] for r in spec['repos']], ['shop'])
        doms = spec['repos'][0]['domains']
        self.assertEqual([d['name'] for d in doms], ['c0', 'c1'])
        self.assertEqual([s['name'] for s in doms[0]['services']], ['app.py'])
        leaves = doms[0]['services'][0]['leaves']
        self.assertEqual([(l['name'], l['kind'], l['loc']) for l in leaves],
                         [('main()', 1, 'app.py:3'), ('Server', 2, 'app.py:9')])
        self.assertEqual([l['name'] for l in doms[1]['services'][0]['leaves']], ['URL', 'query()'])

    def test_edges(self):
        # ids: services app.py=0, db.py=1; leaves main()=2, Server=3, URL=4, query()=5
        spec = build()
        self.assertEqual(spec['edges'], [[0, 1, 0], [2, 5, 0], [3, 4, 3]])

    def test_folder_groups(self):
        doms = build(group='folder')['repos'][0]['domains']
        self.assertEqual([d['name'] for d in doms], ['(root)', 'lib'])

    def test_merged_graph_splits_by_repo(self):
        g = json.loads(json.dumps(GRAPH))
        for n in g['nodes']:
            if n['source_file'].startswith('lib/'): n['repo'] = 'core'
        spec = build(g)
        self.assertEqual([r['name'] for r in spec['repos']], ['core', 'shop'])
        self.assertIn([1, 0, 0], spec['edges'])  # app.py (shop, now 1) imports db.py (core, now 0)

    def test_same_names_get_numbered(self):
        g = {'nodes': [node('a', 'index.js', 'a/index.js', 1), node('b', 'index.js', 'b/index.js', 1),
                       node('a_f', 'f()', 'a/index.js', 2, _callable=True),
                       node('a_f2', 'f()', 'a/index.js', 8, _callable=True)], 'links': []}
        svcs = build(g)['repos'][0]['domains'][0]['services']
        self.assertEqual([s['name'] for s in svcs], ['index.js', 'index.js (2)'])
        self.assertEqual([l['name'] for l in svcs[0]['leaves']], ['f()', 'f() (2)'])

    @unittest.skipUnless(shutil.which('node'), 'needs node')
    def test_atlas_accepts_it(self):
        script = ("import {validateSpec} from './src/model/spec.js';"
                  "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>"
                  "console.log(JSON.stringify(validateSpec(JSON.parse(s)))))")
        out = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ATLAS, check=True,
                             input=json.dumps(build()), capture_output=True, text=True).stdout
        self.assertEqual(json.loads(out), [])


if __name__ == '__main__':
    unittest.main()
