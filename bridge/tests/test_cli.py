import contextlib
import io
import json
import os
import tempfile
import unittest

from atlas_bridge.cli import GraphInput, main

from .helpers import FIXTURES, GOLDEN, load

API = os.path.join(FIXTURES, 'graphify', 'api.json')
WEB = os.path.join(FIXTURES, 'graphify', 'web.json')


class CliTest(unittest.TestCase):
    def test_golden_spec(self):
        """test/fixtures/graphify-shop.json (used by Atlas's e2e tests) is exactly what the bridge writes."""
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'spec.json')
            with contextlib.redirect_stderr(io.StringIO()) as err:
                main(['spec', f'api={API}', f'web={WEB}', '--title', 'Shop, mapped by Graphify', '-o', out])
            self.assertEqual(load(out), load(GOLDEN))
            self.assertIn('2 repos, 5 files, 11 symbols, 10 links', err.getvalue())

    def test_stdout_and_folder_grouping(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            main(['spec', '--group', 'folder', API])
        spec = json.loads(out.getvalue())
        self.assertEqual([r['name'] for r in spec['repos']], ['api'])
        self.assertEqual([d['name'] for d in spec['repos'][0]['domains']], ['app'])

    def test_input_names(self):
        self.assertEqual(GraphInput.default_name('/x/shop/graphify-out/graph.json'), 'shop')
        self.assertEqual(GraphInput.default_name('/x/web.json'), 'web')
        self.assertEqual(GraphInput.parse('core=/x/graph.json'), GraphInput('core', '/x/graph.json'))


if __name__ == '__main__':
    unittest.main()
