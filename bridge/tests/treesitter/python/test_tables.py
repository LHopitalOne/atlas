import unittest

from atlas_bridge.adapters.treesitter.kit import TestPathPolicy
from atlas_bridge.adapters.treesitter.python.syntax import PythonSyntax
from atlas_bridge.adapters.treesitter.python.workspace import ModuleIndex, ModuleTable

from .support import node, workspace


class ModuleTableTest(unittest.TestCase):
    def test_reads_names_through_methods(self):
        ws = workspace({'pkg/a.py': 'from .b import L\nimport os\nX = 1\nX = 2\ndef f(): pass\nclass K: pass\n'})
        table = ModuleTable(ws.source('pkg/a.py'))
        self.assertEqual([PythonSyntax.text(v) for _, v in table.assignments('X')], ['1', '2'])
        self.assertEqual(table.assignments('missing'), ())
        self.assertEqual(PythonSyntax.name(table.function('f')), 'f')
        self.assertEqual(PythonSyntax.name(table.class_definition('K')), 'K')
        self.assertIsNone(table.function('K'))
        self.assertEqual(table.imported('L').attr, 'L')
        self.assertIsNone(table.imported('os').attr)
        self.assertFalse(hasattr(table, 'imports'))


class ImportedFromTest(unittest.TestCase):
    def test_from_imports_resolve_to_file_and_attribute(self):
        ws = workspace(
            {
                'pkg/a.py': 'from .b import L as M\nfrom nowhere import N\nimport pkg.b\n',
                'pkg/b.py': 'L = []\n',
            }
        )
        a = ws.source('pkg/a.py')
        found = ws.names.imported_from(a, 'M')
        self.assertEqual((found[0].path, found[1]), ('pkg/b.py', 'L'))
        self.assertIsNone(ws.names.imported_from(a, 'N'))  # not in the repository
        self.assertIsNone(ws.names.imported_from(a, 'pkg'))  # a module import, no attribute
        self.assertIsNone(ws.names.imported_from(a, 'missing'))
        self.assertEqual(ws.names.dotted_module('pkg.b').path, 'pkg/b.py')
        self.assertIsNone(ws.names.dotted_module('pkg.c'))


class ModuleIndexPolicyTest(unittest.TestCase):
    def test_ranking_uses_the_injected_policy(self):
        ws = workspace({'scripts/util.py': '', 'tests/x/util.py': '', 'app/longer_name/util.py': ''})

        class Nothing(TestPathPolicy):
            def is_test(self, path):
                return False

        default = ModuleIndex(ws.sources, TestPathPolicy())
        self.assertEqual(default.dotted('util').path, 'scripts/util.py')  # tooling is production when ranking
        self.assertEqual(ModuleIndex(ws.sources, Nothing()).dotted('util').path, 'scripts/util.py')
        self.assertEqual(ws.names.dotted_module('util').path, 'scripts/util.py')


class SelfNamesTest(unittest.TestCase):
    def test_is_self(self):
        ws = workspace({'m.py': 'self.a\ncls.b\nother.c\n(self).d\n'})
        m = ws.source('m.py')
        self.assertTrue(PythonSyntax.is_self(node(m, 'identifier', 'self')))
        self.assertTrue(PythonSyntax.is_self(node(m, 'identifier', 'cls')))
        self.assertFalse(PythonSyntax.is_self(node(m, 'identifier', 'other')))
        self.assertFalse(PythonSyntax.is_self(node(m, 'parenthesized_expression', '(self)')))
        self.assertFalse(PythonSyntax.is_self(None))
