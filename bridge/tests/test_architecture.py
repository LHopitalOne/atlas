"""Guards the structure rules of the package (see README, 'Code rules'). Each test names the rule it checks."""

import ast
import glob
import os
import unittest

from atlas_bridge.core import errors

PACKAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'atlas_bridge')
MAX_MODULE_LINES = 300
MAX_CLASS_LINES = 250
MAX_FUNCTION_LINES = 50
ERRORS = {name for name, obj in vars(errors).items() if isinstance(obj, type) and issubclass(obj, errors.BridgeError)}
REGEX_CALLS = {'compile', 'match', 'search', 'sub', 'subn', 'split', 'findall', 'finditer', 'fullmatch'}
# Modules still being rewritten into packages. Empty when the rewrite is done; nothing may be added to it.
LEGACY = set()


def modules():
    for path in sorted(glob.glob(os.path.join(PACKAGE, '**', '*.py'), recursive=True)):
        rel = os.path.relpath(path, PACKAGE)
        if rel not in LEGACY:
            with open(path, encoding='utf-8') as f:
                source = f.read()
            yield rel, source, ast.parse(source)


class ArchitectureTest(unittest.TestCase):
    def test_init_files_only_import_and_export(self):
        """__init__.py holds a docstring, imports and __all__, nothing else."""
        for rel, _, tree in modules():
            if os.path.basename(rel) != '__init__.py':
                continue
            for i, node in enumerate(tree.body):
                docstring = i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                exports = isinstance(node, ast.Assign) and [ast.unparse(t) for t in node.targets] == ['__all__']
                ok = docstring or exports or isinstance(node, ast.Import | ast.ImportFrom)
                self.assertTrue(ok, f'{rel}:{node.lineno} has {type(node).__name__}; move it out of __init__.py')

    def test_modules_classes_and_functions_stay_small(self):
        for rel, source, tree in modules():
            self.assertLessEqual(source.count('\n'), MAX_MODULE_LINES, f'{rel} is a god file; split it')
            for node in ast.walk(tree):
                size = getattr(node, 'end_lineno', 0) - getattr(node, 'lineno', 0) + 1
                if isinstance(node, ast.ClassDef):
                    self.assertLessEqual(size, MAX_CLASS_LINES, f'{rel}: class {node.name} has {size} lines')
                elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    self.assertLessEqual(size, MAX_FUNCTION_LINES, f'{rel}: {node.name}() has {size} lines')

    def test_only_bridge_errors_are_raised(self):
        """Every `raise X(...)` uses a class from core/errors.py; bare re-raises are fine."""
        for rel, _, tree in modules():
            for node in ast.walk(tree):
                if isinstance(node, ast.Raise) and node.exc is not None:
                    exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                    name = exc.attr if isinstance(exc, ast.Attribute) else getattr(exc, 'id', '')
                    self.assertIn(name, ERRORS, f'{rel}:{node.lineno} raises {name}; use a BridgeError subclass')

    def test_regexes_are_named_constants(self):
        """re.<fn>(...) runs only on a compiled, named pattern: re.compile appears only as an UPPER_CASE
        module or class constant, and no other re function is called directly."""
        for rel, _, tree in modules():
            constants = {
                id(n.value)
                for n in ast.walk(tree)
                if isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)
            }
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if getattr(node.func.value, 'id', None) != 're' or node.func.attr not in REGEX_CALLS:
                    continue
                self.assertTrue(
                    node.func.attr == 'compile' and id(node) in constants,
                    f'{rel}:{node.lineno} calls re.{node.func.attr} inline; make it a named, commented constant',
                )

    def test_legacy_list_only_shrinks(self):
        for rel in LEGACY:
            self.assertTrue(os.path.exists(os.path.join(PACKAGE, rel)), f'{rel} is gone; remove it from LEGACY')


if __name__ == '__main__':
    unittest.main()
