import dataclasses
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
        self.assertEqual(caller['id'], 'web::src_api_placeorder')  # the id Graphify gives placeOrder in src/api.js
        g = CodeGraph()
        GraphifyReader(g).read(out, 'unused')
        self.assertEqual(sorted(g.files), [('api', 'app/main.py'), ('web', 'src/api.js')])
        self.assertEqual(list(g.links.values()), [Status.MATCHED])


class GraphifyShapeTest(unittest.TestCase):
    """The edges take Graphify's HTTP endpoint shape, so its own tools read them like the ones it extracts."""

    SERVED = {
        'nodes': MERGED['nodes']
        + [
            {'id': 'api::app_main', 'label': 'main.py', 'repo': 'api', 'source_file': 'app/main.py'},
            {
                'id': 'api::app_main_post_order',
                'label': 'post_order()',
                'repo': 'api',
                'source_file': 'app/main.py',
                'source_location': 'L11',
                '_callable': True,
            },
        ],
        'links': [],
    }

    def test_caller_calls_endpoint_and_endpoint_serves_handler(self):
        out = GraphifyLinkWriter(self.SERVED).present(LINKS[:1])
        call, serve = out['links']
        self.assertEqual(
            (call['source'], call['relation'], call['target']),
            ('web::src_api_placeorder', 'calls_endpoint', 'api::http:POST /orders'),
        )
        self.assertEqual(
            (serve['source'], serve['relation'], serve['target']),
            ('api::http:POST /orders', 'serves', 'api::app_main_post_order'),
        )
        self.assertEqual({call['context'], serve['context']}, {'http'})
        self.assertEqual(call['metadata']['atlas']['reason'], 'named target, one route fits')
        endpoint = next(n for n in out['nodes'] if n['id'] == 'api::http:POST /orders')
        self.assertEqual(endpoint['type'], 'http_endpoint')
        self.assertEqual(endpoint['metadata']['http_endpoint']['methods'], ['POST'])

    def test_no_serves_edge_when_the_handler_name_is_not_unique(self):
        twice = dict(self.SERVED, nodes=self.SERVED['nodes'] + [dict(self.SERVED['nodes'][-1], id='api::other')])
        out = GraphifyLinkWriter(twice).present(LINKS[:1])
        self.assertEqual([e['relation'] for e in out['links']], ['calls_endpoint'])

    def test_rubric_confidences(self):
        out = GraphifyLinkWriter(MERGED).present(LINKS)
        self.assertEqual([e['confidence_score'] for e in out['links']], [1.0, 0.75])

    def test_writing_twice_adds_nothing_twice(self):
        once = GraphifyLinkWriter(self.SERVED).present(LINKS)
        twice = GraphifyLinkWriter(once).present(LINKS)
        self.assertEqual(twice['links'], once['links'])
        self.assertEqual(sorted(n['id'] for n in twice['nodes']), sorted(n['id'] for n in once['nodes']))

    def test_one_edge_per_caller_and_endpoint_the_most_certain(self):
        guess = Link(CALL, 'web', 'api', ROUTE, Status.AMBIGUOUS, 'a guess')
        out = GraphifyLinkWriter(MERGED).present([guess, LINKS[0], guess])
        self.assertEqual(
            [(e['confidence'], e['metadata']['atlas']['reason']) for e in out['links']],
            [
                ('EXTRACTED', 'named target, one route fits'),
            ],
        )

    def test_endpoint_ids_never_land_on_code(self):
        clash = {'id': 'api::http_post_orders', 'label': 'orders()', 'repo': 'api', 'source_file': 'http/post.py'}
        out = GraphifyLinkWriter(dict(MERGED, nodes=MERGED['nodes'] + [clash])).present(LINKS[:1])
        self.assertEqual(out['links'][0]['target'], 'api::http:POST /orders')

    def test_no_serves_edge_in_a_graph_of_one_repository(self):
        base = {'nodes': [{k: v for k, v in n.items() if k != 'repo'} for n in self.SERVED['nodes']], 'links': []}
        out = GraphifyLinkWriter(base).present(LINKS[:1])
        self.assertEqual([e['relation'] for e in out['links']], ['calls_endpoint'])

    def test_serves_only_a_handler_read_from_the_code(self):
        named = dataclasses.replace(ROUTE, framework='named')
        read = dataclasses.replace(ROUTE, framework='read')
        for route, expected in ((named, []), (read, [('serves', 'INFERRED')])):
            out = GraphifyLinkWriter(self.SERVED).present([dataclasses.replace(LINKS[0], route=route)])
            serves = [(e['relation'], e['confidence']) for e in out['links'] if e['relation'] == 'serves']
            self.assertEqual(serves, expected)

    def test_output_of_the_earlier_writer_is_replaced(self):
        old = {'id': 'api::http:POST /orders', 'label': 'POST /orders', 'repo': 'api'}
        edge = {'source': 'web::src_api_placeorder', 'target': old['id'], 'relation': 'calls_http'}
        out = GraphifyLinkWriter(dict(MERGED, nodes=MERGED['nodes'] + [old], links=[edge])).present(LINKS[:1])
        self.assertEqual([e['relation'] for e in out['links']], ['calls_endpoint'])
        self.assertEqual(sum(n['id'] == old['id'] for n in out['nodes']), 1)


class SingleRepoGraphTest(unittest.TestCase):
    """A graph from `graphify update` on one repository: its nodes carry no `repo`."""

    def test_each_call_starts_at_its_own_function(self):
        base = {'nodes': [{k: v for k, v in n.items() if k != 'repo'} for n in MERGED['nodes']], 'links': []}
        later = Call('web', 'src/api.js', 2, P('/orders'), 'POST', 'later')  # the graph is older: lines moved
        handler = Call('web', 'src/api.js', 12, P('/orders'), 'POST', '')  # an anonymous callback
        unknown = Call('web', 'src/other.js', 3, P('/orders'), 'POST', 'one')
        other = Call('web', 'src/other.js', 7, P('/orders'), 'POST', 'two')
        links = [Link(c, 'web', 'api', ROUTE, Status.MATCHED, 'r') for c in (CALL, later, handler, unknown, other)]
        out = GraphifyLinkWriter(base).present(links)
        self.assertEqual(
            [e['source'] for e in out['links']],
            [
                'web::src_api_placeorder',
                'web::src_api_later',
                'web::src_api',
                'web::src_other_one',
                'web::src_other_two',
            ],
        )


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
        kafka = {**found['links'][0]['call'], 'protocol': 'kafka', 'path': '/events'}
        found['links'].append({**found['links'][0], 'call': kafka})  # an HTTP key does not judge a Kafka topic
        report = score.score(key, found)
        self.assertEqual([r['found'] for r in report['scopes']['prod']], [True, False])
        self.assertEqual(
            report['summary'],
            {
                'prod_recall': '1/2',
                'precision': '1/2',
                'false_links': 1,
                'links_to_excluded_calls': 1,
                'other_protocols_not_judged': 1,
                'prod_confirmed_by_scip': '0/2',
            },
        )
        self.assertEqual(report['unmatched_calls'], 1)


if __name__ == '__main__':
    unittest.main()
