import unittest

from atlas_bridge.adapters.treesitter.javascript.calls.clients import ClientFetch, RequestMethods
from atlas_bridge.adapters.treesitter.javascript.calls.composite import RequestCalls
from atlas_bridge.adapters.treesitter.javascript.calls.direct import DirectRequests
from atlas_bridge.adapters.treesitter.javascript.calls.verbs import VerbRequests
from atlas_bridge.adapters.treesitter.javascript.extractor import JavaScriptExtractor
from atlas_bridge.adapters.treesitter.javascript.routes.express import ExpressRoutes
from atlas_bridge.adapters.treesitter.kit import CallCollector, LanguageExtractor, RouteCollector

from .support import Repository

SOURCE = (
    'const app = express();\n'
    "app.get('/orders/:id', show);\n"
    "fetch('/direct');\n"
    "api.fetch('/client-fetch');\n"
    "api.request('/request-method');\n"
    "api.get('/verb');\n"
)


workspace = Repository.workspace


def paths(extraction):
    return sorted(str(c.path) for c in extraction.calls)


class CollectorTest(unittest.TestCase):
    def test_the_extractor_follows_the_kit(self):
        self.assertTrue(issubclass(JavaScriptExtractor, LanguageExtractor))
        self.assertTrue(issubclass(ExpressRoutes, RouteCollector))
        for idiom in (*RequestCalls.IDIOMS, RequestCalls):
            self.assertTrue(issubclass(idiom, CallCollector), idiom)
        self.assertTrue(JavaScriptExtractor().handles('src/a.tsx'))
        self.assertFalse(JavaScriptExtractor().handles('src/a.py'))

    def test_each_idiom_finds_its_own_requests(self):
        ws = workspace([('src/a.js', SOURCE)])
        self.assertEqual(paths(DirectRequests(ws).collect()), ['/direct'])
        self.assertEqual(paths(ClientFetch(ws).collect()), ['/client-fetch'])
        self.assertEqual(paths(RequestMethods(ws).collect()), ['/request-method'])
        self.assertEqual(paths(VerbRequests(ws).collect()), ['/verb'])  # app.get(...) is a route
        self.assertEqual(
            [str(c.path) for c in RequestCalls(ws).collect().calls],
            ['/direct', '/client-fetch', '/request-method', '/verb'],  # source order
        )
        self.assertEqual([str(r.path) for r in ExpressRoutes(ws).collect().routes], ['/orders/{id}'])

    def test_composite_claims_like_its_idioms(self):
        ws = workspace([('src/a.js', SOURCE)])
        module = ws.module(ws.sources[0])
        composite = RequestCalls(ws)
        claimed = [site.name for site in module.sites() if composite.claims(module, site)]
        self.assertEqual(claimed, ['fetch', 'fetch', 'request', 'get'])

    def test_files_without_requests_are_not_scanned(self):
        ws = workspace([('src/a.js', 'const x = 1;\n'), ('src/b.js', "fetch('/b');\n"), ('src/c.ts', 'baseUrl;\n')])
        self.assertEqual([s.path for s in ws.scanned()], ['src/b.js', 'src/c.ts'])
        self.assertIsNot(ws.module(ws.sources[1]), ws.module(ws.sources[1]))  # each pass reads a file anew

    def test_test_code_by_path_and_block(self):
        ws = workspace([('src/a.spec.js', "fetch('/a');\n"), ('src/b.js', "it('x', () => fetch('/b'));\n")])
        self.assertEqual([c.test for c in RequestCalls(ws).collect().calls], [True, True])
        self.assertTrue(ws.is_test(ws.sources[0]))
        self.assertFalse(ws.is_test(ws.sources[1]))


if __name__ == '__main__':
    unittest.main()
