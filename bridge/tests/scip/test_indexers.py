import os
import tempfile
import unittest
from unittest import mock

from atlas_bridge.adapters.scip import PythonScipIndexer, RustScipIndexer, TypeScriptScipIndexer
from atlas_bridge.adapters.scip.indexers import ScipIndexer
from atlas_bridge.core.errors import IndexerFailedError, IndexerUnavailableError


class WritesIndex(ScipIndexer):
    """A stand-in indexer: python3 writing (or failing to write) the output file."""

    TOOL, LANGUAGE, MARKERS = 'python3', 'fake', ('marker',)

    def __init__(self, code="open(out, 'w').write('x')"):
        self._code = code

    def command(self, name, root, out, scratch):
        return ['python3', '-c', f'out = {out!r}\n{self._code}']


class IndexersTest(unittest.TestCase):
    def test_markers(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(RustScipIndexer().applies(d))
            open(os.path.join(d, 'Cargo.toml'), 'w').close()
            self.assertTrue(RustScipIndexer().applies(d))
            self.assertFalse(PythonScipIndexer().applies(d))

    def test_commands_never_run_repository_code(self):
        with tempfile.TemporaryDirectory() as d:
            rust = RustScipIndexer().command('relay', d, 'out.scip', d)
            with open(rust[rust.index('--config-path') + 1]) as f:
                config = f.read()
            self.assertIn('"buildScripts": {"enable": false}', config)
            self.assertIn('"procMacro": {"enable": false}', config)
            self.assertIn('--infer-tsconfig', TypeScriptScipIndexer().command('web', d, 'o', d))
            open(os.path.join(d, 'tsconfig.json'), 'w').close()
            self.assertNotIn('--infer-tsconfig', TypeScriptScipIndexer().command('web', d, 'o', d))
        python = PythonScipIndexer()
        self.assertIn('--project-name', python.command('sentry', '.', 'o', '.'))
        self.assertIn('--max-old-space-size', python.environment()['NODE_OPTIONS'])

    def test_running(self):
        with tempfile.TemporaryDirectory() as d:
            out = WritesIndex().index('shop', d, d)
            self.assertEqual(out, os.path.join(os.path.abspath(d), 'shop.fake.scip'))
            with self.assertRaises(IndexerFailedError):
                WritesIndex('raise SystemExit("boom")').index('shop', d, d)
            with self.assertRaises(IndexerFailedError):
                WritesIndex('pass').index('other', d, d)  # exits 0 but writes nothing
            with mock.patch('shutil.which', return_value=None), self.assertRaises(IndexerUnavailableError):
                WritesIndex().index('shop', d, d)


if __name__ == '__main__':
    unittest.main()
