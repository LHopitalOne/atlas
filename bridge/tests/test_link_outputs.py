import importlib.util
import os
import unittest

from atlas_bridge.adapters import GraphifyLinkWriter, GraphifyReader, LinkFilePresenter
from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import CodeGraph, Status
from atlas_bridge.usecases.link import Link, LinkReport

from .helpers import ATLAS

P = PathTemplate.parse
ROUTE = Route('api', 'app/main.py', 10, P('/orders'), frozenset({'POST'}), 'post_order', '', 'fastapi')
CALL = Call('web', 'src/api.js', 5, P('/orders'), 'POST', 'placeOrder', frozenset({'BASE'}))
PAYLOAD = Call('sentry', 'sources.py', 3, None, kind='payload', route_name='dsyms')
DSYMS = Route('sentry', 'urls.py', 8, P('/dsyms'), name='dsyms')
LINKS = [
    Link(CALL, 'web', 'api', ROUTE, Status.MATCHED, 'named target, one route fits'),
    Link(CALL, 'web', 'api', None, Status.UNMATCHED, 'nothing'),
    Link(PAYLOAD, 'symbolicator', 'sentry', DSYMS, Status.INFERRED, 'payload'),
]
MERGED = {
    'graph': {'graphify_version': '0.9.102'},
    'nodes': [
        {'id': 'web::src_api', 'label': 'api.js', 'repo': 'web', 'source_file': 'src/api.js', 'source_location': 'L1'},
        {
            'id': 'web::src_api_placeorder',
            'label': 'placeOrder()',
            'repo': 'web',
            'source_file': 'src/api.js',
            'source_location': 'L4',
            '_callable': True,
        },
        {
            'id': 'web::src_api_later',
            'label': 'later()',
            'repo': 'web',
            'source_file': 'src/api.js',
            'source_location': 'L9',
            '_callable': True,
        },
    ],
    'links': [],
}


class WithLinksTest(unittest.TestCase):
    def test_adds_endpoints_and_edges_to_a_merged_graph(self):
        out = GraphifyLinkWriter(MERGED).present(LINKS)
        edges = [(e['source'], e['target'], e['confidence']) for e in out['links']]
        self.assertEqual(
            edges,
            [
                ('web::src_api_placeorder', 'api::http:POST /orders', 'EXTRACTED'),
                ('symbolicator::http-client', 'sentry::http:ANY /dsyms', 'INFERRED'),
            ],
        )
        self.assertEqual(out['graph'], MERGED['graph'])
        self.assertEqual(len(MERGED['nodes']), 3)  # input untouched

    def test_without_a_graph_and_through_to_atlas(self):
        out = GraphifyLinkWriter().present(LINKS[:1])
        caller = [n for n in out['nodes'] if n['repo'] == 'web'][0]
        self.assertEqual(caller['id'], 'web::src/api.js::placeOrder')
        g = CodeGraph()
        GraphifyReader(g).read(out, 'unused')
        self.assertEqual(sorted(g.files), [('api', 'app/main.py'), ('web', 'src/api.js')])
        self.assertEqual(list(g.links.values()), [Status.MATCHED])


class LinkFileTest(unittest.TestCase):
    def test_present(self):
        ex = Extraction([ROUTE], [CALL, Call('web', 't.js', 1, P('/x'), test=True)])
        out = LinkFilePresenter().present(LinkReport(['api', 'web'], ex, LINKS))
        self.assertEqual(out['repos']['web'], {'routes': 0, 'calls': 1, 'test_calls': 1})
        self.assertEqual(out['links'][0]['route']['methods'], ['POST'])
        self.assertEqual(out['links'][1]['route'], None)
        self.assertEqual(out['links'][2]['caller'], 'symbolicator')
        self.assertIsNone(out['links'][2]['call']['path'])


def load_score():
    spec = importlib.util.spec_from_file_location('score', os.path.join(ATLAS, 'eval', 'score.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScoreTest(unittest.TestCase):
    def test_score(self):
        score = load_score()
        key = {
            'links': [
                {
                    'id': 'L1',
                    'scope': 'prod',
                    'caller': 'web',
                    'target': 'api',
                    'method': 'POST',
                    'path': '/orders/',
                    'how_the_path_is_known': 'literal',
                    'route': {'file': 'app/main.py', 'line': 11},
                },
                {
                    'id': 'L2',
                    'scope': 'prod',
                    'caller': 'web',
                    'target': 'api',
                    'method': 'GET',
                    'path': '/users/{id}',
                    'how_the_path_is_known': 'template',
                    'route': {'file': 'app/users.py', 'line': 3},
                },
            ],
            'excluded': [{'caller': 'web', 'file': 'test/x.js', 'line': 2}],
        }
        found = LinkFilePresenter().present(LinkReport(['api', 'web'], Extraction(), LINKS[:2]))
        found['links'].append(
            {
                **found['links'][0],
                'call': {**found['links'][0]['call'], 'file': 'test/x.js', 'line': 2},
                'route': {**found['links'][0]['route'], 'path': '/other', 'line': 99},
            }
        )
        found['links'].append(
            {**found['links'][0], 'route': {**found['links'][0]['route'], 'path': '/nope', 'line': 99}}
        )
        report = score.score(key, found)
        self.assertEqual([r['found'] for r in report['scopes']['prod']], [True, False])
        self.assertEqual(
            report['summary'],
            {
                'prod_recall': '1/2',
                'precision': '1/2',
                'false_links': 1,
                'links_to_excluded_calls': 1,
                'prod_confirmed_by_scip': '0/2',
            },
        )
        self.assertEqual(report['unmatched_calls'], 1)


if __name__ == '__main__':
    unittest.main()
