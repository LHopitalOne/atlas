import time
import unittest

from atlas_bridge.adapters.treesitter.rust.guard import StackGuard

from .support import RustRepo


class RobustnessTest(unittest.TestCase):
    def test_cycles_terminate(self):
        found = RustRepo(
            {
                'src/a.rs': (
                    'fn a() -> Router { b().route("/a", get(h)) }\n'
                    'fn b() -> Router { a().route("/b", get(h)) }\n'
                    'const A: &str = B;\nconst B: &str = A;\n'
                    'fn f() { client.get(A); }\n'
                    'fn m() -> MethodRouter { n() }\nfn n() -> MethodRouter { m() }\n'
                    'fn r() -> Router { Router::new().route(A, get(h)).route("/x", m()) }\n'
                    'fn me() -> MethodRouter { me() }\nfn s() -> Router { Router::new().route("/y", me()) }\n'
                )
            }
        ).extract()
        self.assertEqual(sorted((str(r.path), r.handler) for r in found.routes), [('/x', 'm'), ('/y', 'me')])
        self.assertEqual(found.calls, [])

    def test_malformed_files(self):
        found = RustRepo(
            {
                'empty.rs': b'',
                'bytes.rs': b'fn f() { client.get("/a\xff/b"); }\n'
                b'fn r() -> Router { Router::new().route("/x", get(h)) }',
                'broken.rs': b'}}}{{{ fn ( Router .route( "/x" , get( ',
                'digit.rs': 'fn f() { client.get(format!("/a/{²}/{}", x, y)); }'.encode(),
            }
        ).extract()
        self.assertEqual([str(r.path) for r in found.routes], ['/x'])
        self.assertEqual(sorted(str(c.path) for c in found.calls), ['/a/{param}/{x}', '/a�/b'])

    def test_deep_nesting(self):
        n = 1500
        found = RustRepo(
            {
                'src/concat.rs': 'fn f() { client.get("/a"' + ' + "/b"' * n + '); }\n',
                'src/elseif.rs': 'fn g() { client.post(if a { "/c" }'
                + ' else if b { "/d" }' * n
                + ' else { "/e" }); }\n',
                'src/blocks.rs': 'fn h() { client.put(' + '{ ' * n + '"/f"' + ' }' * n + '); }\n',
                'src/pass.rs': 'fn k() { client.patch("/g"' + '.to_string()' * n + '); }\n',
                'src/use.rs': 'use ' + 'a::{' * n + 'b' + '}' * n + ';\n',
            }
        ).calls()
        self.assertEqual(found[('GET', '/a' + '/b' * n)].line, 1)
        self.assertIn(('POST', '/c'), found)
        self.assertIn(('PUT', '/f'), found)
        self.assertEqual(sorted(found), [('GET', '/a' + '/b' * n), ('POST', '/c'), ('PUT', '/f')])

    def test_many_lookups_in_one_function(self):
        source = 'fn f() {\n' + ''.join(f'    let k{i} = x;\n    m.get(k{i});\n' for i in range(2000)) + '}\n'
        start = time.perf_counter()
        self.assertEqual(RustRepo(source).calls(), {})
        self.assertLess(time.perf_counter() - start, 5)

    def test_stack_exhaustion_costs_one_piece(self):
        def deep():
            raise RecursionError

        self.assertEqual(StackGuard.run(deep), [])
        self.assertEqual(StackGuard.run(len, [1, 2]), 2)


if __name__ == '__main__':
    unittest.main()
