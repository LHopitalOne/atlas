import contextlib
import io
import os
import tempfile
import unittest

from atlas_bridge.cli import Aliases, App, GraphInput, JsonFile, NamedInput, RepositoryInput
from atlas_bridge.core.errors import (
    AliasError,
    BridgeError,
    ExtractionError,
    GraphFormatError,
    InputError,
    NamedInputError,
    ParserUnavailableError,
    RepositoryNotFoundError,
    SourceReadError,
)
from atlas_bridge.usecases.link import ServiceNames


class HierarchyTest(unittest.TestCase):
    def test_every_error_is_a_bridge_error(self):
        for cls in (NamedInputError, AliasError, RepositoryNotFoundError, GraphFormatError):
            self.assertTrue(issubclass(cls, InputError))
        for cls in (ParserUnavailableError, SourceReadError):
            self.assertTrue(issubclass(cls, ExtractionError))
        self.assertTrue(issubclass(InputError, BridgeError) and issubclass(ExtractionError, BridgeError))

    def test_message_and_hint(self):
        e = ParserUnavailableError('rust')
        self.assertEqual(e.message, 'no tree-sitter grammar for rust')
        self.assertIn("pip install 'atlas-bridge[links]'", str(e))
        self.assertEqual(str(SourceReadError('a.py', 'gone')), 'cannot read a.py: gone')
        self.assertEqual(InputError('x').exit_code, 2)
        self.assertEqual(ExtractionError('x').exit_code, 1)


class InputsTest(unittest.TestCase):
    def test_named_inputs(self):
        self.assertEqual(NamedInput.parse('a=b'), NamedInput('a', 'b'))
        for bad in ('=b', 'a='):
            with self.assertRaises(NamedInputError):
                NamedInput.parse(bad)

    def test_aliases(self):
        self.assertEqual(Aliases.parse(['upstream=sentry']), {'upstream': 'sentry'})
        for bad in ('upstream', '=sentry', 'upstream='):
            with self.assertRaises(AliasError):
                Aliases.parse([bad])
        with self.assertRaises(AliasError):
            ServiceNames(['relay'], {'upstream': 'sentry'})  # sentry is not part of the run

    def test_repository_must_exist(self):
        with self.assertRaises(RepositoryNotFoundError):
            RepositoryInput.parse('/no/such/folder').checked()

    def test_graph_files(self):
        with tempfile.TemporaryDirectory() as d:
            bad, missing = os.path.join(d, 'bad.json'), os.path.join(d, 'missing.json')
            with open(bad, 'w') as f:
                f.write('{not json')
            with self.assertRaises(GraphFormatError):
                GraphInput.parse(bad).load()
            with self.assertRaises(GraphFormatError):
                JsonFile.read(missing)


class AppTest(unittest.TestCase):
    def run_app(self, *argv):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = App().run(list(argv))
        return code, err.getvalue()

    def test_input_errors_exit_2_with_a_message(self):
        with tempfile.TemporaryDirectory() as d:
            graph = os.path.join(d, 'g.json')
            JsonFile.write(graph, {'edges': []})
            code, err = self.run_app('spec', graph)
        self.assertEqual(code, 2)
        self.assertIn('is not a Graphify graph: it has no "nodes" list', err)
        code, err = self.run_app('links', '/no/such/folder')
        self.assertEqual(code, 2)
        self.assertIn("no repository folder at '/no/such/folder'", err)


if __name__ == '__main__':
    unittest.main()
