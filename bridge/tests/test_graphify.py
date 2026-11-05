import copy
import unittest

from atlas_bridge.adapters import GraphifyReader
from atlas_bridge.core.model import CodeGraph, Community, Kind, Ref, Status

from .helpers import GRAPH, node


def read(data=GRAPH, repo='shop'):
    g = CodeGraph()
    GraphifyReader(g).read(data, repo)
    return g


class GraphifyReadTest(unittest.TestCase):
    def test_files_and_symbols(self):
        g = read()
        self.assertEqual(sorted(g.files), [('shop', 'app.py'), ('shop', 'lib/db.py')])
        app = g.files[('shop', 'app.py')]
        self.assertEqual(
            [(s.name, s.kind, s.line) for s in app.symbols], [('main()', Kind.FUNCTION, 3), ('Server', Kind.CLASS, 9)]
        )
        self.assertEqual([s.name for s in g.files[('shop', 'lib/db.py')].symbols], ['URL', 'query()'])
        self.assertEqual(g.tools, {'Graphify 0.9.101'})

    def test_links_skip_structure_externals_and_comments(self):
        g = read()
        self.assertEqual(
            g.links,
            {
                (Ref('shop', 'app.py', 'app_main'), Ref('shop', 'lib/db.py', 'db_query')): Status.MATCHED,
                (Ref('shop', 'app.py', 'app_server'), Ref('shop', 'lib/db.py', 'db_url')): Status.INFERRED,
                (Ref('shop', 'app.py'), Ref('shop', 'lib/db.py')): Status.MATCHED,
            },
        )

    def test_majority_community(self):
        data = {
            'nodes': [
                node('a', 'a.py', 'a.py', 1, community=4),
                node('f', 'f()', 'a.py', 2, community=7, _callable=True),
                node('g', 'g()', 'a.py', 3, community=7, _callable=True),
            ]
        }
        self.assertEqual(read(data).files[('shop', 'a.py')].community, Community(7, 'c7'))

    def test_no_community(self):
        data = {'nodes': [{'id': 'a', 'label': 'a.md', 'source_file': 'a.md', 'file_type': 'document'}]}
        self.assertIsNone(read(data).files[('shop', 'a.md')].community)

    def test_nodes_name_their_repo_after_merge_graphs(self):
        data = copy.deepcopy(GRAPH)
        for n in data['nodes']:
            if n['source_file'].startswith('lib/'):
                n['repo'] = 'core'
        g = read(data)
        self.assertEqual(sorted(g.files), [('core', 'lib/db.py'), ('shop', 'app.py')])
        self.assertIn((Ref('shop', 'app.py'), Ref('core', 'lib/db.py')), g.links)

    def test_unknown_version_and_confidence(self):
        data = {
            'nodes': [node('a', 'a.py', 'a.py', 1), node('b', 'b.py', 'b.py', 1)],
            'edges': [{'source': 'a', 'target': 'b', 'relation': 'calls'}],
        }
        g = read(data)
        self.assertEqual(g.tools, {'Graphify'})
        self.assertEqual(list(g.links.values()), [Status.INFERRED])


if __name__ == '__main__':
    unittest.main()
