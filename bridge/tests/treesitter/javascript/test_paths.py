import unittest

from atlas_bridge.adapters.treesitter.javascript.routes.paths import ExpressPath
from atlas_bridge.adapters.treesitter.kit import RepositoryFiles

from .support import Repository


class ExpressPathTest(unittest.TestCase):
    def test_express_path(self):
        self.assertEqual(ExpressPath.canonical('users/:id'), '/users/{id}')
        self.assertEqual(ExpressPath.canonical('/(.*)'), '/{*rest}')
        self.assertEqual(ExpressPath.canonical('/a/files*'), '/a/{*rest}')
        self.assertEqual(ExpressPath.canonical('/:from-:to'), '/{from}-{to}')
        self.assertEqual(ExpressPath.canonical('/post/:date{[0-9]{1,3}}'), '/post/{date}')

    def test_named_wildcards(self):
        self.assertEqual(ExpressPath.canonical('/splat/*rest'), '/splat/{*rest}')
        self.assertEqual(ExpressPath.canonical('/splat/*'), '/splat/{*rest}')
        self.assertEqual(ExpressPath.canonical('/splat/*-'), '/splat/{*rest}')

    def test_join(self):
        self.assertEqual(ExpressPath.join('/api/', '/x'), '/api/x')
        self.assertEqual(ExpressPath.join('', 'x'), 'x')


class FilesTest(unittest.TestCase):
    def test_precheck_and_size(self):
        big = 'x' * (RepositoryFiles.MAX_BYTES + 1)
        self.assertEqual(Repository({'a.js': 'const x = 1;\n', 'b.js': big}).extract().calls, [])

    def test_extension_grammar(self):
        for ext in ('.mjs', '.cjs', '.jsx', '.ts', '.tsx'):
            self.assertIn(('GET', '/a'), Repository.calls("fetch('/a');", 'src/a' + ext))


if __name__ == '__main__':
    unittest.main()
