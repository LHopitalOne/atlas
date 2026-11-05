import unittest

from atlas_bridge.adapters.treesitter.kit import Grammar, SourceFile
from atlas_bridge.adapters.treesitter.rust.source import RustFile
from atlas_bridge.adapters.treesitter.rust.syntax import RustSyntax
from atlas_bridge.adapters.treesitter.rust.uses import UseTree


class CountingGrammar:
    """A grammar that counts how often it parses."""

    def __init__(self):
        self._grammar = Grammar.for_path('a.rs')
        self.parses = 0

    def parse(self, data):
        self.parses += 1
        return self._grammar.parse(data)

    def query(self, source):
        return self._grammar.query(source)


def rust_file(source, path='src/api/mod.rs', grammar=None, test=False):
    return RustFile(SourceFile(path, source.encode(), grammar or Grammar.for_path(path), test))


class RustFileTest(unittest.TestCase):
    def test_nothing_is_parsed_until_asked(self):
        grammar = CountingGrammar()
        f = rust_file('use actix_web::web;\nfn a() { b(c(d())); }\n', grammar=grammar)
        self.assertEqual((f.module, f.parts), ('api', frozenset({'src', 'api', 'mod'})))
        self.assertEqual(grammar.parses, 0)
        self.assertEqual(f.framework, 'actix')
        self.assertEqual(len(f.nodes('call')), 3)
        self.assertEqual(grammar.parses, 1)

    def test_captures_are_in_source_order(self):
        source = 'fn a() {\n' + ''.join(f'    x{i}(y{i}(z{i}()));\n' for i in range(40)) + '}\n'
        for _ in range(3):
            calls = rust_file(source).nodes('call')
            starts = [(c.start_byte, -c.end_byte) for c in calls]
            self.assertEqual(starts, sorted(starts))
            self.assertEqual(len(calls), 120)

    def test_state_is_read_only(self):
        f = rust_file('fn a() {}\n', path='src/lib.rs')
        for name in ('module', 'parts', 'framework', 'tested'):
            with self.assertRaises(AttributeError):
                setattr(f, name, 'x')
        self.assertEqual((f.module, f.framework, f.tested), ('src', 'axum', False))

    def test_inner_cfg_test_makes_the_file_test_code(self):
        self.assertTrue(rust_file('#![cfg(test)]\nfn a() {}\n').tested)
        self.assertTrue(rust_file('fn a() {}\n', test=True).tested)

    def test_later_use_overrides_an_earlier_one(self):
        f = rust_file('use a::get;\nuse b::{get, post as p};\n')
        self.assertEqual((f.imported('get'), f.imported('p'), f.imported('x', 'd')), ('b::get', 'b::post', 'd'))

    def test_outer_calls(self):
        f = rust_file('fn a() { make().send(); }\n')
        inner = next(c for c in f.nodes('call') if RustSyntax.method(c) is None)
        self.assertTrue(f.has_outer_call(inner))
        self.assertEqual(f.text(f.outer_call(inner)), 'make().send()')


class UseTreeTest(unittest.TestCase):
    def test_returns_the_names_a_use_brings_in(self):
        f = rust_file('use axum::routing::{get, head as axum_head, nested::{put}};\n')
        arg = f.nodes('use')[0].child_by_field_name('argument')
        self.assertEqual(
            UseTree.read(arg),
            {'get': 'axum::routing::get', 'axum_head': 'axum::routing::head', 'put': 'axum::routing::nested::put'},
        )


if __name__ == '__main__':
    unittest.main()
