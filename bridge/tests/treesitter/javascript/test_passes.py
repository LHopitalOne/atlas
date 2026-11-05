import unittest

from atlas_bridge.adapters.treesitter.javascript.calls.composite import RequestCalls
from atlas_bridge.adapters.treesitter.javascript.calls.direct import DirectRequests
from atlas_bridge.adapters.treesitter.javascript.calls.verbs import VerbRequests
from atlas_bridge.adapters.treesitter.javascript.collector import FileCollector, SharedPass
from atlas_bridge.adapters.treesitter.javascript.extractor import JavaScriptExtractor
from atlas_bridge.adapters.treesitter.javascript.policy import JavaScriptTestPolicy
from atlas_bridge.adapters.treesitter.javascript.routes.express import ExpressRoutes
from atlas_bridge.adapters.treesitter.javascript.source import JsSource
from atlas_bridge.core.http import Extraction

from .support import Repository

FILES = [
    ('src/app.js', "const app = express();\napp.get('/x', show);\n"),
    ('src/b.js', "fetch('/b');\n"),
    ('src/c.js', "fetch('/c');\n"),
]


def calls(extraction):
    return [(c.method, str(c.path)) for c in extraction.calls]


class TreeSpy(FileCollector):
    """Records, as each file is read, which files of the workspace still hold their syntax tree."""

    def start(self):
        self.held = []

    def read(self, module):
        self.held.append([s.path for s in self.workspace.sources if s.parsed])

    def finish(self):
        return Extraction()


class FilePassTest(unittest.TestCase):
    def test_the_extractor_reads_every_file_in_one_pass(self):
        ws = Repository.workspace(FILES)
        (shared,) = JavaScriptExtractor().collectors(ws)
        self.assertIsInstance(shared, SharedPass)
        self.assertEqual([type(c) for c in shared.collectors], [ExpressRoutes, RequestCalls])
        out = shared.collect()
        self.assertEqual([str(r.path) for r in out.routes], ['/x'])
        self.assertEqual(calls(out), [('GET', '/b'), ('GET', '/c')])

    def test_trees_are_dropped_unless_a_file_declares_routes(self):
        ws = Repository.workspace(FILES)
        spy = TreeSpy(ws)
        SharedPass(ws, (ExpressRoutes(ws), RequestCalls(ws), spy)).collect()
        self.assertEqual(
            spy.held,
            [['src/app.js'], ['src/app.js', 'src/b.js'], ['src/app.js', 'src/c.js']],  # b.js is gone by c.js
        )
        self.assertEqual([s.path for s in ws.sources if s.parsed], [])  # every tree is dropped once the pass ends
        self.assertTrue(all(isinstance(s, JsSource) for s in ws.sources))

    def test_a_collector_can_run_again(self):
        ws = Repository.workspace(FILES)
        collector = RequestCalls(ws)
        self.assertEqual(calls(collector.collect()), calls(collector.collect()))
        routes = ExpressRoutes(ws)
        self.assertEqual(len(routes.collect().routes), 1)
        self.assertEqual(len(routes.collect().routes), 1)

    def test_collectors_do_not_depend_on_what_ran_before(self):
        source = (
            "const X = '/x';\nconst a5 = X;\nconst a4 = a5;\nconst a3 = a4;\nconst a2 = a3;\nconst a1 = a2;\n"
            'api.get(a1);\nfetch(a5);\n'
        )
        ws = Repository.workspace([('a.js', source)])
        # one pass of every idiom resolves a1 first: a5 is reached at the depth limit, and stays unresolved
        self.assertEqual(calls(RequestCalls(ws).collect()), [])
        self.assertEqual(calls(DirectRequests(ws).collect()), [('GET', '/x')])
        VerbRequests(ws).collect()
        self.assertEqual(calls(DirectRequests(ws).collect()), [('GET', '/x')])
        self.assertEqual(calls(RequestCalls(ws).collect()), [])


class ScenarioPolicy(JavaScriptTestPolicy):
    TEST_FUNCS = JavaScriptTestPolicy.TEST_FUNCS | {'scenario'}


class ScenarioExtractor(JavaScriptExtractor):
    POLICY = ScenarioPolicy


class PolicyTest(unittest.TestCase):
    def test_the_workspace_uses_the_extractors_policy(self):
        files = {'src/a.js': "scenario('x', () => fetch('/a'));\nfetch('/b');\n"}
        repo = Repository(files)
        self.assertEqual({str(c.path): c.test for c in repo.extract().calls}, {'/a': False, '/b': False})
        ws = ScenarioExtractor().workspace('web', Repository.workspace(list(files.items())).sources)
        self.assertEqual({str(c.path): c.test for c in RequestCalls(ws).collect().calls}, {'/a': True, '/b': False})


if __name__ == '__main__':
    unittest.main()
