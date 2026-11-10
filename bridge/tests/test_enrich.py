"""Files described by a model (usecases/enrich.py), what it is shown and how its answer is read
(adapters/muse/prompt.py), and the descriptions on the map (AtlasSpecPresenter). No request leaves the machine."""

import os
import tempfile
import unittest
import unittest.mock

from atlas_bridge.adapters.atlas import AtlasSpecPresenter
from atlas_bridge.adapters.muse import FilePrompt, MuseDescriber
from atlas_bridge.core.descriptions import Description
from atlas_bridge.core.errors import JudgeUnavailableError
from atlas_bridge.core.model import CodeGraph, Kind, Symbol
from atlas_bridge.usecases.draw import MapDrawer
from atlas_bridge.usecases.enrich import Enricher
from atlas_bridge.usecases.ports import FileCase, FileDescriber


class Echo(FileDescriber):
    """Describes every file as an api about its own name; records what it was asked."""

    def __init__(self, role='api'):
        self.role, self.asked = role, []

    def describe(self, cases):
        self.asked += cases
        return [Description(f'Serves {c.path}.', self.role, ('a', 'b', 'c', 'd', 'e')) for c in cases]


def graph():
    g = CodeGraph()
    g.file('web', 'src/app.ts')
    g.file('api', 'api/orders.py').symbols = [Symbol('o', 'create', Kind.FUNCTION, 3)]
    g.file('api', 'tests/test_orders.py')
    return g


class EnricherTest(unittest.TestCase):
    def test_link_ends_first_then_the_biggest_files_and_tests_skipped(self):
        echo = Echo()
        found = Enricher(echo, skip=lambda p: p.startswith('tests/')).describe(
            graph(), frozenset({('web', 'src/app.ts')})
        )
        self.assertEqual([(c.repo, c.path) for c in echo.asked], [('web', 'src/app.ts'), ('api', 'api/orders.py')])
        self.assertEqual(found[('api', 'api/orders.py')].tags, ('a', 'b', 'c', 'd'))

    def test_tags_are_not_repeated_nor_the_role_again(self):
        class Twice(Echo):
            def describe(self, cases):
                return [Description('x', 'auth', ('auth', 'mfa', 'mfa', 'recovery')) for _ in cases]

        found = Enricher(Twice()).describe(graph())
        self.assertEqual(found[('api', 'api/orders.py')].tags, ('mfa', 'recovery'))

    def test_a_budget_and_a_role_outside_the_list(self):
        echo = Echo()
        Enricher(echo, max_files=1).describe(graph())
        self.assertEqual(len(echo.asked), 1)
        self.assertEqual(Enricher(Echo(role='wizard')).describe(graph()), {})


class FilePromptTest(unittest.TestCase):
    def test_reads_the_file_and_the_answer(self):
        folder = tempfile.mkdtemp()
        os.makedirs(os.path.join(folder, 'api'))
        with open(os.path.join(folder, 'api', 'orders.py'), 'w') as f:
            f.write('def create(): ...\n')
        prompt = FilePrompt({'api': folder})
        messages = prompt.messages(FileCase('api', 'api/orders.py'))
        self.assertIn('def create', messages[1]['content'])
        self.assertIsNone(prompt.messages(FileCase('api', 'missing.py')))
        answer = '{"summary": "Creates orders.", "role": "api", "tags": ["Orders", " "]}'
        self.assertEqual(FilePrompt.description(answer), Description('Creates orders.', 'api', ('orders',)))
        self.assertIsNone(FilePrompt.description('not json'))

    def test_no_key_is_a_clear_error(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(JudgeUnavailableError):
            MuseDescriber({})


class DescribedSpecTest(unittest.TestCase):
    def test_a_described_file_has_doc_and_tags_and_the_meta_names_the_model(self):
        g = graph()
        described = {('api', 'api/orders.py'): Description('Creates orders.', 'api', ('orders',))}
        spec = AtlasSpecPresenter('t', None, described, 'meta/muse-ember').present(MapDrawer().draw(g))
        services = {s['loc']: s for r in spec['repos'] for d in r['domains'] for s in d['services']}
        self.assertEqual(services['api/orders.py:1']['doc'], 'Creates orders.')
        self.assertEqual(services['api/orders.py:1']['tags'], ['api', 'orders'])
        self.assertNotIn('doc', services['src/app.ts:1'])
        self.assertEqual((spec['meta']['docSource'], spec['meta']['docModel']), ('ai', 'meta/muse-ember'))


if __name__ == '__main__':
    unittest.main()
