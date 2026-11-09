import unittest

from atlas_bridge.adapters.treesitter.python.calls import Condition, MethodOptions
from atlas_bridge.adapters.treesitter.python.scope import Scope
from atlas_bridge.adapters.treesitter.python.syntax import PythonSyntax
from atlas_bridge.adapters.treesitter.python.values import PythonValueResolver
from atlas_bridge.core.http import ANY

from .support import node, workspace


def expr(text):
    source = workspace({'m.py': f'x = {text}\n'}).source('m.py')
    return source.root.named_children[0].named_children[0].child_by_field_name('right')


class ConditionTest(unittest.TestCase):
    def test_truth_of_literals(self):
        truth = Condition.literal_truth
        self.assertFalse(truth(expr('None')))
        self.assertFalse(truth(expr('0.0')))
        self.assertTrue(truth(expr('10')))
        self.assertFalse(truth(expr("''")))
        self.assertTrue(truth(expr('[1]')))
        self.assertTrue(truth(expr('f()')))

    def test_conditions_over_arguments(self):
        cond = Condition({'a': expr('None'), 'b': expr('1')}, {'c': None, 'd': expr("'x'")})
        self.assertTrue(cond.truth(expr('a is None')))
        self.assertFalse(cond.truth(expr('b is None')))
        self.assertTrue(cond.truth(expr('not (a)')))
        self.assertIsNone(cond.truth(expr('not c')))
        self.assertTrue(cond.truth(expr('d or e')))
        self.assertIsNone(cond.truth(expr('c or e')))
        self.assertFalse(cond.truth(expr('a or a')))
        self.assertIsNone(cond.truth(expr('a == None')))
        self.assertIsNone(cond.truth(expr('c is None')))
        self.assertIsNone(cond.truth(expr('()')))
        self.assertIsNone(cond.truth(expr('1 + 1')))
        self.assertTrue(cond.truth(expr("d == 'x'")))
        self.assertFalse(cond.truth(expr("'y' == d")))
        self.assertTrue(cond.truth(expr("d != 'y'")))
        self.assertIsNone(cond.truth(expr("b == 'x'")))  # not a string argument
        self.assertIsNone(cond.truth(expr("c == 'x'")))  # no value
        self.assertIsNone(cond.truth(expr('d == e')))
        self.assertTrue(Condition.over(expr('a and b'), {'a', 'b'}))
        self.assertFalse(Condition.over(None, {'a'}))


class MethodOptionsTest(unittest.TestCase):
    def test_method_arguments_and_choices(self):
        ws = workspace({'m.py': 'def f(method, data):\n    g(method, "/x")\n    h(("post"))\n    k(1)\n'})
        m = ws.source('m.py')
        methods = MethodOptions(ws, PythonValueResolver(ws))
        param = node(m, 'identifier', 'method')
        call = next(n for n in PythonSyntax.walk(m.root, ('call',)))
        scope = Scope.at(m, call)
        arg = call.child_by_field_name('arguments').named_children[0]
        self.assertTrue(methods.is_method_arg(scope, arg))
        self.assertFalse(methods.is_method_arg(scope, node(m, 'integer', '1')))
        self.assertEqual(methods.options(scope, node(m, 'parenthesized_expression', '("post")')), ['POST'])
        self.assertEqual(methods.options(Scope.module(m), param), [ANY])
        self.assertEqual(methods.decide(ANY, None, {}, {}), ANY)
