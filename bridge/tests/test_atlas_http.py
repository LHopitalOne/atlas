"""HTTP links on the Atlas map: endpoints, edges, proofs with code, origins and accuracy (adapters/atlas/http.py).

test/fixtures/http-shop.json (used by Atlas's e2e tests for the proof and impact panels) is exactly what this
writes. Regenerate it after an intended change with:
    cd bridge && python -c "from tests.test_atlas_http import write_golden; write_golden()"
"""

import contextlib
import io
import json
import os
import tempfile
import unittest

from atlas_bridge.adapters import GraphifyReader
from atlas_bridge.adapters.atlas import AtlasSpecPresenter, CodeSource, HttpLayer, LinkFile, RepoOrigin
from atlas_bridge.adapters.atlas.http import Endpoint
from atlas_bridge.cli import main
from atlas_bridge.core.errors import LinkFormatError
from atlas_bridge.core.model import CodeGraph
from atlas_bridge.usecases.draw import MapDrawer

from .helpers import ATLAS, FIXTURES, load
from .test_atlas import validate

LINKS = os.path.join(FIXTURES, 'shop-links.json')
SHOP = os.path.join(FIXTURES, 'shop')
HTTP_GOLDEN = os.path.join(ATLAS, 'test', 'fixtures', 'http-shop.json')
ORIGINS = {
    'api': RepoOrigin('https://github.com/example/shop-api', '1111111111111111111111111111111111111111'),
    'web': RepoOrigin('https://github.com/example/shop-web', '2222222222222222222222222222222222222222'),
}
ACCURACY = {'found': 2, 'of': 2, 'falseLinks': 0, 'scip': 1, 'how': 'A hand-made key for the test shop.'}


def http_spec():
    graph = CodeGraph()
    reader = GraphifyReader(graph)
    for name in ('api', 'web'):
        reader.read(load(os.path.join(FIXTURES, 'graphify', f'{name}.json')), name)
    folders = {name: os.path.join(SHOP, name) for name in ('api', 'web')}
    http = HttpLayer(LinkFile(LINKS).parse(load(LINKS)), CodeSource(folders, ORIGINS), ACCURACY)
    http.add_files(graph)
    return AtlasSpecPresenter('Shop, with HTTP links', http).present(MapDrawer().draw(graph))


def write_golden():
    with open(HTTP_GOLDEN, 'w', encoding='utf-8') as f:
        json.dump(http_spec(), f, indent=1)
        f.write('\n')


def names(spec):
    """Node names in id order (services first, then leaves), as Atlas numbers them."""
    services = [s for r in spec['repos'] for d in r['domains'] for s in d['services']]
    return [s['name'] for s in services] + [lf['name'] for s in services for lf in s.get('leaves', [])]


class HttpSpecTest(unittest.TestCase):
    def setUp(self):
        self.spec = http_spec()
        self.names = names(self.spec)

    def test_golden(self):
        self.assertEqual(self.spec, load(HTTP_GOLDEN))

    def test_endpoints_are_leaves_on_the_route_file(self):
        main = next(
            s for r in self.spec['repos'] for d in r['domains'] for s in d['services'] if s['name'] == 'main.py'
        )
        endpoints = [lf for lf in main['leaves'] if lf['kind'] == 2]
        self.assertEqual([e['name'] for e in endpoints], ['POST /orders', 'GET /orders/{order_id}'])
        self.assertEqual(endpoints[0]['loc'], 'app/main.py:10')
        self.assertEqual(self.spec['meta']['kind'][2], 'HTTP endpoint')

    def test_each_link_joins_the_sending_function_to_its_endpoint(self):
        got = [(self.names[lk['from']], self.names[lk['to']], lk['proof']) for lk in self.spec['links']]
        self.assertEqual(
            got, [('placeOrder()', 'POST /orders', 'scip'), ('loadOrder()', 'GET /orders/{order_id}', 'inferred')]
        )
        edges = {(a, b): st for a, b, st in self.spec['edges']}
        self.assertEqual([edges[(lk['from'], lk['to'])] for lk in self.spec['links']], [0, 3])

    def test_proof_carries_code_and_origins(self):
        call, route = self.spec['links'][0]['call'], self.spec['links'][0]['route']
        self.assertEqual((call['file'], call['line'], call['start']), ('src/api.js', 5, 3))
        self.assertIn('fetch(`${BASE}/orders`', call['code'][2])
        self.assertEqual((route['handler'], route['framework'], route['methods']), ('post_order', 'fastapi', ['POST']))
        self.assertEqual(self.spec['links'][0]['checks'][0]['verdict'], 'confirmed')
        self.assertEqual(self.spec['repos'][0]['url'], 'https://github.com/example/shop-api')
        self.assertEqual(self.spec['meta']['accuracy'], ACCURACY)

    def test_requests_with_no_route_are_listed_not_drawn(self):
        (u,) = self.spec['unmatched']
        self.assertEqual((self.names[u['from']], u['method'], u['path']), ('loadUser()', 'GET', '/users/{id}'))

    def test_atlas_accepts_it(self):
        self.assertEqual(validate(self.spec), [])


class SpecCommandTest(unittest.TestCase):
    def test_spec_with_links_repos_and_accuracy(self):
        with tempfile.TemporaryDirectory() as d:
            out, acc = os.path.join(d, 'spec.json'), os.path.join(d, 'acc.json')
            with open(acc, 'w', encoding='utf-8') as f:
                json.dump(ACCURACY, f)
            graphs = [f'{n}={os.path.join(FIXTURES, "graphify", n + ".json")}' for n in ('api', 'web')]
            repos = [f'--repo={n}={os.path.join(SHOP, n)}' for n in ('api', 'web')]
            with contextlib.redirect_stderr(io.StringIO()) as err:
                main(['spec', *graphs, '--links', LINKS, *repos, '--accuracy', acc, '-o', out])
            spec = load(out)
        self.assertIn('2 HTTP links', err.getvalue())
        self.assertEqual(len(spec['links']), 2)
        self.assertEqual(spec['links'][0]['call']['code'], http_spec()['links'][0]['call']['code'])

    def test_accuracy_must_be_an_object(self):
        with tempfile.TemporaryDirectory() as d:
            acc = os.path.join(d, 'acc.json')
            with open(acc, 'w', encoding='utf-8') as f:
                json.dump([1, 2], f)
            graph = f'api={os.path.join(FIXTURES, "graphify", "api.json")}'
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['spec', graph, '--links', LINKS, '--accuracy', acc, '-o', os.path.join(d, 's.json')])


class LinkFileTest(unittest.TestCase):
    def test_bad_files_say_what_is_wrong(self):
        with self.assertRaises(LinkFormatError):
            LinkFile('x.json').parse({'repos': {}})
        with self.assertRaises(LinkFormatError):
            LinkFile('x.json').parse({'links': [{'caller': 'web'}]})
        with self.assertRaises(LinkFormatError):
            LinkFile('x.json').parse(
                {'links': [{'caller': 'web', 'status': 'maybe', 'call': {'file': 'a', 'line': 1}}]}
            )

    def test_test_calls_are_left_out(self):
        data = load(LINKS)
        data['links'][0]['call']['test'] = True
        self.assertEqual(len(LinkFile().parse(data)), len(data['links']) - 1)


class SourceTest(unittest.TestCase):
    def test_remotes_become_web_addresses(self):
        self.assertEqual(RepoOrigin.web_url('git@github.com:getsentry/relay.git'), 'https://github.com/getsentry/relay')
        self.assertEqual(
            RepoOrigin.web_url('https://github.com/openedx/credentials.git'), 'https://github.com/openedx/credentials'
        )
        self.assertEqual(RepoOrigin.web_url(''), '')

    def test_snippets_stay_inside_the_repository(self):
        src = CodeSource({'api': os.path.join(SHOP, 'api')})
        self.assertEqual(src.snippet('api', '../web/src/api.js', 1), (0, []))
        self.assertEqual(src.snippet('nope', 'x.py', 1), (0, []))
        start, lines = src.snippet('api', 'app/main.py', 1)
        self.assertEqual(start, 1)
        self.assertTrue(lines)

    def test_a_folder_outside_git_has_no_origin(self):
        self.assertEqual(RepoOrigin.of(os.path.join(FIXTURES, 'nowhere')), RepoOrigin())


if __name__ == '__main__':
    unittest.main()


class ChannelLinkTest(unittest.TestCase):
    """A Kafka topic has no method and its name is not a URL path: it reads as 'KAFKA events'."""

    KAFKA = {
        'caller': 'sentry',
        'target': 'snuba',
        'status': 'inferred',
        'call': {'file': 'backend.py', 'line': 233, 'method': 'ANY', 'path': '/events', 'protocol': 'kafka'},
        'route': {
            'repo': 'snuba',
            'file': 'errors.yaml',
            'line': 399,
            'methods': ['ANY'],
            'path': '/events',
            'handler': 'events',
            'framework': 'named',
            'protocol': 'kafka',
        },
    }

    def test_label_and_leaf(self):
        (record,) = LinkFile().parse({'links': [self.KAFKA]})
        self.assertEqual(record.route.label, 'KAFKA events')
        self.assertEqual(Endpoint(record.route).leaf()['doc'], 'KAFKA channel served by events (named).')

    def test_http_routes_keep_method_and_path(self):
        http = dict(self.KAFKA, route=dict(self.KAFKA['route'], protocol='http', methods=['POST']))
        (record,) = LinkFile().parse({'links': [http]})
        self.assertEqual(record.route.label, 'POST /events')
