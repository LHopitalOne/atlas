import unittest

from atlas_bridge.adapters.treesitter.python.scope import Scope
from atlas_bridge.adapters.treesitter.python.syntax import PythonSyntax
from atlas_bridge.adapters.treesitter.python.workspace import AbsoluteModule, RelativeModule

from .support import node, workspace


class ModuleIndexTest(unittest.TestCase):
    def test_modules_by_dotted_suffix_production_first(self):
        ws = workspace(
            {
                'src/app/utils/snuba.py': 'X = 1\n',
                'tests/app/utils/snuba.py': 'X = 2\n',
                'src/app/__init__.py': '',
                '__init__.py': '',
            }
        )
        names = ws.names
        self.assertEqual(names.locate(AbsoluteModule('utils.snuba')).path, 'src/app/utils/snuba.py')
        self.assertEqual(names.locate(AbsoluteModule('app')).path, 'src/app/__init__.py')
        self.assertEqual(names.locate(RelativeModule('src/app')).path, 'src/app/__init__.py')
        self.assertEqual(
            names.locate(RelativeModule('src/app').child('utils').child('snuba')).path, 'src/app/utils/snuba.py'
        )
        self.assertIsNone(names.locate(AbsoluteModule('nowhere')))


class NameLookupTest(unittest.TestCase):
    def test_values_functions_classes_modules_and_imports(self):
        ws = workspace(
            {
                'pkg/a.py': (
                    'import os.path\nimport json as j\nfrom .b import B, f as g\nfrom . import b\n'
                    'X = 1\nX = 2\ndef h(): pass\n@d\nclass K: pass\nuse = b.f\np = os.path\n'
                ),
                'pkg/b.py': 'B = "b"\ndef f(): pass\n',
            }
        )
        a = ws.source('pkg/a.py')
        lookup = ws.names.lookup
        self.assertEqual(PythonSyntax.text(lookup(a, 'X').node), '2')
        self.assertTrue(lookup(a, 'h').is_function)
        self.assertTrue(lookup(a, 'K').is_class)
        self.assertTrue(lookup(a, 'os').is_module)
        self.assertEqual(lookup(a, 'j').ref.name, 'json')
        self.assertEqual(PythonSyntax.text(lookup(a, 'B').node), '"b"')
        self.assertTrue(lookup(a, 'g').is_function)
        self.assertTrue(lookup(a, 'b').is_module)
        self.assertIsNone(lookup(a, 'missing'))
        self.assertIsNone(lookup(a, 'X', depth=99))
        self.assertTrue(ws.names.expression(a, node(a, 'attribute', 'b.f')).is_function)
        self.assertIsNone(ws.names.value(a, node(a, 'attribute', 'os.path')))

    def test_module_level_reads_see_earlier_assignments(self):
        ws = workspace({'m.py': "BASE = 'http://x'\nBASE = BASE + '/api'\nlate = LATE\nLATE = 'l'\n"})
        m = ws.source('m.py')
        use = [n for n in PythonSyntax.walk(m.root, ('identifier',)) if PythonSyntax.text(n) == 'BASE'][2]
        self.assertEqual(PythonSyntax.text(ws.names.lookup(m, 'BASE', before=use.start_byte).node), "'http://x'")
        late = node(m, 'identifier', 'LATE')
        self.assertEqual(PythonSyntax.text(ws.names.lookup(m, 'LATE', before=late.start_byte).node), "'l'")


class ScopeAndTestCodeTest(unittest.TestCase):
    def test_scope_and_test_functions(self):
        ws = workspace({'m.py': 'class C:\n    def m(self):\n        x = 1\ndef test():\n    y = 2\nz = 3\n'})
        m = ws.source('m.py')
        self.assertEqual(Scope.at(m, node(m, 'integer', '1')).qualified, 'C.m')
        self.assertEqual(Scope.at(m, node(m, 'integer', '3')).qualified, '')
        self.assertTrue(ws.is_test(m, node(m, 'integer', '2')))
        self.assertFalse(ws.is_test(m, node(m, 'integer', '1')))
        self.assertFalse(ws.is_test(m))
        self.assertEqual([PythonSyntax.name(c) for _, c in ws.classes('C')], ['C'])


class SyntaxTest(unittest.TestCase):
    def test_parameters_and_methods(self):
        ws = workspace(
            {
                'm.py': (
                    'class C:\n    @staticmethod\n    def s(a: int, b=1, c: str = "x", *args, **kw):\n        pass\n'
                    '    def m(self):\n        pass\n'
                    'def f():\n    pass\n'
                )
            }
        )
        m = ws.source('m.py')
        funcs = {PythonSyntax.name(f): f for f in PythonSyntax.walk(m.root, ('function_definition',))}
        self.assertEqual([p for p, _ in PythonSyntax.params(funcs['s'])], ['a', 'b', 'c'])
        self.assertFalse(PythonSyntax.is_method(funcs['s']))
        self.assertTrue(PythonSyntax.is_method(funcs['m']))
        self.assertFalse(PythonSyntax.is_method(funcs['f']))
        self.assertEqual(PythonSyntax.args(None), ([], {}))
        self.assertIsNone(PythonSyntax.docstring(None))
