import contextlib
import io
import os
import tempfile
import unittest
from unittest import mock

from atlas_bridge.cli import App, ScipInput, main
from atlas_bridge.cli import index as index_command
from atlas_bridge.core.errors import RepositoryNotFoundError

from .helpers import FIXTURES, load
from .scip.builder import ScipBuilder
from .scip.test_indexers import WritesIndex

SHOP = os.path.join(FIXTURES, 'shop')


class ScipCliTest(unittest.TestCase):
    def test_links_with_scip(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'web.typescript.scip'), 'wb') as f:
                f.write(ScipBuilder().occurrence('src/api.js', 1, 'x y web 1 src/BASE.', definition=True).build())
            out = os.path.join(d, 'links.json')
            with contextlib.redirect_stderr(io.StringIO()) as err:
                main(['links', f'api={SHOP}/api', f'web={SHOP}/web', '-o', out, '--scip-dir', d])
            found = load(out)
        self.assertIn('SCIP: 0 links confirmed, 2 read from syntax alone', err.getvalue())
        matched = [lk for lk in found['links'] if lk['status'] == 'matched']
        self.assertEqual({lk['verification'] for lk in matched}, {'syntax'})
        unmatched = [lk for lk in found['links'] if lk['status'] == 'unmatched']
        self.assertEqual({lk['verification'] for lk in unmatched}, {'unverified'})

    def test_scip_inputs(self):
        self.assertEqual(ScipInput.parse('/x/sentry.python.scip'), ScipInput('sentry', '/x/sentry.python.scip'))
        self.assertEqual(ScipInput.parse('relay=/x/i.scip').name, 'relay')
        with self.assertRaises(RepositoryNotFoundError):
            ScipInput.in_folder('/no/such/folder')

    def test_index_command(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(index_command, 'INDEXERS', (WritesIndex,)):
            repo = os.path.join(d, 'shop')
            os.makedirs(repo)
            open(os.path.join(repo, 'marker'), 'w').close()
            empty = os.path.join(d, 'empty')
            os.makedirs(empty)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = App().run(['index', repo, empty, '-o', os.path.join(d, 'out')])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.exists(os.path.join(d, 'out', 'shop.fake.scip')))
            self.assertIn('empty: no indexer applies', err.getvalue())


if __name__ == '__main__':
    unittest.main()
