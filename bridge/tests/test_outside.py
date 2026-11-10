"""Requests that leave the repositories (usecases/outside.py), browser calls to a route the server lacks
(usecases/within.py NoRouteRule), and the resources pages load from other sites (kit/pages.py)."""

import os
import shutil
import tempfile
import unittest

from atlas_bridge.adapters.atlas import HttpLayer, LinkFile
from atlas_bridge.adapters.treesitter.kit import PageTags, RepositoryFiles, UrlTemplate
from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import CodeGraph, Ref, Status
from atlas_bridge.usecases.link import LinkFinder
from atlas_bridge.usecases.outside import OutsideRule
from atlas_bridge.usecases.within import NoRouteRule, WithinRepoRule

P = PathTemplate.parse
ROUTES = [
    Route('web', 'api/chats.py', 10, P('/api/v1/chats/pinned'), frozenset({'GET'})),
    Route('web', 'api/chats.py', 20, P('/api/v1/chats/{id}'), frozenset({'GET'})),
]


def request(url, file='src/api.ts', repo='web'):
    u = UrlTemplate.split(url)
    return Call(repo, file, 3, P(u.path), 'GET', 'f', frozenset(u.hints))


def find(*calls, repos=('web',)):
    rules = (*LinkFinder.RULES[:-1], WithinRepoRule, LinkFinder.RULES[-1])
    finder = LinkFinder(list(repos), None, False, rules, (OutsideRule, NoRouteRule))
    return [(lk.status, lk.target, lk.route is not None) for lk in finder.find(Extraction(ROUTES, list(calls)))]


class OutsideTest(unittest.TestCase):
    def test_a_public_host_no_repository_serves_is_outside(self):
        self.assertEqual(find(request('https://api.linkedin.com/v2/me')), [(Status.OUTSIDE, 'api.linkedin.com', False)])

    def test_local_placeholder_and_own_hosts_are_not_outside(self):
        for url in (
            'http://localhost:8080/x/y',
            'http://10.0.0.5/x/y',
            'https://api.example.com/x/y',
            'http://web.internal/x',
        ):
            self.assertEqual(find(request(url)), [], url)
        self.assertEqual(find(request('https://web.acme.io/v2/me')), [])  # its name says it is the web repository

    def test_a_service_name_is_not_a_host(self):
        self.assertEqual(request('http://api:8000/orders').host, '')
        self.assertEqual(request('https://API.LinkedIn.com/v2/me').host, 'api.linkedin.com')


class NoRouteTest(unittest.TestCase):
    def test_browser_call_under_the_servers_prefix_with_no_route(self):
        self.assertEqual(find(request('/api/v1/chats/pinned')), [(Status.MATCHED, 'web', True)])
        self.assertEqual(find(request('/api/v1/policies')), [(Status.UNMATCHED, 'web', False)])

    def test_too_little_shared_or_not_browser_code_says_nothing(self):
        self.assertEqual(find(request('/api/other')), [])  # one shared word
        self.assertEqual(find(request('/api/v1/policies', file='worker.py')), [])
        self.assertEqual(find(request('/api/v1/{id}')), [])  # past the prefix, only a value
        self.assertEqual(find(request('/api/v1/chats/me', file='src/a.ts')), [])  # a route of values could take it


class PageTagsTest(unittest.TestCase):
    PAGE = (
        '<html>\n<head>\n<script src="https://telegram.org/js/telegram-web-app.js"></script>\n'
        '<link rel="stylesheet" href="https://cdn.example.org/a.css">\n<script src="/app.js"></script>\n'
        '</head><body><a href="https://t.me/askmonica_bot">Open</a></body></html>\n'
    )

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, 'index.html'), 'w') as f:
            f.write(self.PAGE)
        with open(os.path.join(self.dir, 'Hero.tsx'), 'w') as f:
            f.write('export const Hero = () => <CtaButton variant="solid" href="https://t.me/bot">Go</CtaButton>;\n')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_scripts_styles_and_links_to_other_sites(self):
        calls = PageTags(RepositoryFiles(self.dir)).calls('site')
        found = sorted((c.file, c.line, c.method, c.host, str(c.path)) for c in calls)
        self.assertEqual(
            found,
            [
                ('Hero.tsx', 1, 'LINK', 't.me', '/bot'),
                ('index.html', 3, 'GET', 'telegram.org', '/js/telegram-web-app.js'),
                ('index.html', 4, 'GET', 'cdn.example.org', '/a.css'),
                ('index.html', 6, 'LINK', 't.me', '/askmonica_bot'),
            ],
        )


class OutsideOnTheMapTest(unittest.TestCase):
    def test_an_outside_link_reaches_an_endpoint_of_its_host(self):
        record = {
            'caller': 'bot',
            'target': 'api.linkedin.com',
            'status': 'outside',
            'call': {'file': 'oauth.py', 'line': 108, 'method': 'GET', 'path': '/v2/me'},
            'route': None,
        }
        layer = HttpLayer(LinkFile().parse({'links': [record]}))
        graph = CodeGraph()
        layer.add_files(graph)
        self.assertIn((HttpLayer.OUTSIDE, 'api.linkedin.com'), graph.files)
        (endpoint,) = layer.endpoints(Ref(HttpLayer.OUTSIDE, 'api.linkedin.com'))
        self.assertEqual(endpoint.route.label, 'GET /v2/me')
        self.assertEqual(endpoint.leaf()['doc'], 'HTTP route served by api.linkedin.com (outside service).')
