import unittest

from atlas_bridge.adapters.treesitter.rust.calls import RequestImpl

from .support import RustRepo
from .test_source import rust_file

TRAIT = """
impl UpstreamRequest for Ping {
    fn path(&self) -> Cow<'_, str> { Cow::Borrowed("/api/ping/") }
}
"""
CLIENT = 'fn send(client: Client) { client.get("/api/a/"); }\n'


class CallOrderTest(unittest.TestCase):
    def test_calls_come_file_by_file_trait_impls_first(self):
        repo = RustRepo({'src/a.rs': CLIENT + TRAIT, 'src/b.rs': TRAIT + CLIENT, 'src/c.rs': CLIENT})
        found = [(c.file, str(c.path)) for c in repo.extract().calls]
        self.assertEqual(
            found,
            [
                ('src/a.rs', '/api/ping'),
                ('src/a.rs', '/api/a'),
                ('src/b.rs', '/api/ping'),
                ('src/b.rs', '/api/a'),
                ('src/c.rs', '/api/a'),
            ],
        )

    def test_output_is_the_same_every_run(self):
        files = {f'src/m{i}.rs': CLIENT.replace('/a/', f'/a{i}/') + TRAIT for i in range(5)}
        files['src/app.rs'] = (
            'fn app() -> Router {\n'
            + '    Router::new()\n'
            + ''.join(f'        .route("/r{i}", get(h)).merge(sub{i}())\n' for i in range(10))
            + '}\n'
            + ''.join(f'fn sub{i}() -> Router {{ Router::new().route("/s{i}", get(h)) }}\n' for i in range(10))
        )
        runs = [RustRepo(files).extract() for _ in range(3)]
        self.assertEqual(len({tuple(map(repr, r.routes)) for r in runs}), 1)
        self.assertEqual(len({tuple(map(repr, r.calls)) for r in runs}), 1)


class RequestImplTest(unittest.TestCase):
    def test_only_trait_impls_with_a_body_are_request_impls(self):
        f = rust_file('impl Ping { fn path(&self) {} }\nimpl Up for Ping<T> { fn path(&self) {} }\n')
        inherent, trait = f.nodes('impl')
        self.assertIsNone(RequestImpl.of(inherent))
        request = RequestImpl.of(trait)
        self.assertEqual((request.trait_name, request.type_name), ('Up', 'Ping'))
        self.assertEqual([name for name, _ in request.path_fns()], ['path'])
        with self.assertRaises(AttributeError):
            request.type_name = 'x'


if __name__ == '__main__':
    unittest.main()
