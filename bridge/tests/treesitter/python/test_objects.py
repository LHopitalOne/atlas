"""The value objects are immutable and the resolver's layers are not usable on their own."""

import dataclasses
import unittest

from atlas_bridge.adapters.treesitter.python import values
from atlas_bridge.adapters.treesitter.python.calls import CallSite
from atlas_bridge.adapters.treesitter.python.scope import Scope
from atlas_bridge.adapters.treesitter.python.syntax import PythonSyntax
from atlas_bridge.adapters.treesitter.python.values import Marker, PythonValueResolver, Value
from atlas_bridge.adapters.treesitter.python.values.scoped import ScopeResolver
from atlas_bridge.adapters.treesitter.python.workspace import Symbol

from .support import node, workspace


class ImmutableTest(unittest.TestCase):
    def test_value_scope_and_symbol_cannot_change(self):
        ws = workspace({'m.py': 'X = 1\n'})
        m = ws.source('m.py')
        for obj, field in ((Value('/a'), 'text'), (Scope.module(m), 'func'), (Symbol(Symbol.VALUE), 'node')):
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(obj, field, None)

    def test_call_site_arguments_are_read_only(self):
        ws = workspace({'m.py': 'def w(a, b=1):\n    pass\nw(1, b=2, *rest)\n'})
        m = ws.source('m.py')
        call = node(m, 'call', 'w(1, b=2, *rest)')
        site = CallSite.at(m, call, PythonSyntax.params(node(m, 'function_definition', 'def w(a, b=1):\n    pass')))
        self.assertEqual(sorted(site.bound), ['a', 'b'])
        self.assertTrue(site.splat)
        with self.assertRaises(TypeError):
            site.bound['a'] = None


class ResolverLayersTest(unittest.TestCase):
    def test_only_the_full_resolver_is_concrete_and_exported(self):
        ws = workspace({'m.py': ''})
        with self.assertRaises(TypeError):
            ScopeResolver(ws)
        self.assertNotIn('ScopeResolver', values.__all__)
        resolver = PythonValueResolver(ws)
        for kind in ('identifier', 'string', 'binary_operator', 'call'):
            self.assertIn(kind, resolver.HANDLERS)


class MarkerTest(unittest.TestCase):
    def test_encoding_stays_inside_marker(self):
        filled = Marker.fill(Marker.wrap('p') + '/' + Marker.wrap('q'), {'q': 'x'})
        self.assertTrue(Marker.is_unresolved(filled))
        self.assertTrue(Marker.is_unresolved(Marker.wrap('p')))
        self.assertFalse(Marker.is_unresolved(filled.replace(Marker.UNRESOLVED, '')))
        self.assertEqual(Marker.choice_index(Marker.choice(12)), 12)
        self.assertTrue(Marker.is_choice(Marker.choice(0)) and Marker.is_open(Marker.choice(3)))

    def test_hint_length(self):
        self.assertEqual(len(Value.hint('x' * 500)), Value.HINT_LENGTH)
        self.assertEqual(Value.hint('short'), 'short')
