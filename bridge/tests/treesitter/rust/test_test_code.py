import unittest

from .support import RustRepo


class TestCodeTest(unittest.TestCase):
    def test_loopback_mock_servers_skipped(self):
        source = (
            'fn start_server() -> Url {\n'
            '    let addr = SocketAddr::from(([127, 0, 0, 1], 0));\n'
            '    let router = Router::new().route("/lookup", get(lookup));\n'
            '    serve(addr, router)\n'
            '}\n'
            'fn mock() { let app = Router::new().route("/m", get(m)); bind("localhost:0", app); }\n'
            'fn v4() {\n'
            '    let a = SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0);\n'
            '    let r = Router::new().route("/v", get(v));\n'
            '}\n'
            'fn real() { let app = Router::new().route("/real", get(r)); bind("0.0.0.0:3000", app); }\n'
        )
        self.assertEqual(sorted(RustRepo({'src/local.rs': source}).routes()), [('GET', '/real')])

    def test_test_attributes_with_arguments(self):
        source = (
            '#[tokio::test(flavor = "multi_thread")]\n'
            'async fn t() { client.get("/a"); let r = Router::new().route("/fake", get(h)); }\n'
            '#[cfg(all(test, feature = "x"))]\n'
            'mod tests { fn m() -> Router { Router::new().route("/fake2", get(h)) } fn c() { client.get("/b"); } }\n'
            '#[sqlx::test(migrations = "m")]\nasync fn s() { client.get("/c"); }\n'
            '#[test_case(1)]\nfn u(x: u8) { client.get("/d"); }\n'
            '#[cfg(all(not(test), feature = "x"))]\nfn prod() { client.get("/e"); }\n'
            '#[cfg(any(test, feature = "x"))]\nfn both() { client.get("/f"); }\n'
            'fn app() -> Router { Router::new().route("/real", get(h)) }\n'
        )
        found = RustRepo({'src/a.rs': source}).extract()
        self.assertEqual([str(r.path) for r in found.routes], ['/real'])
        tests = {str(c.path): c.test for c in found.calls}
        self.assertEqual(tests, {'/a': True, '/b': True, '/c': True, '/d': True, '/e': False, '/f': False})

    def test_test_routers_skipped(self):
        found = RustRepo(
            {
                'crates/server-test/src/lib.rs': 'fn mock() -> Router { Router::new().route("/fake", get(f)) }\n',
                'tests/it.rs': 'fn mock() -> Router { Router::new().route("/fake2", get(f)) }\n',
                'src/app.rs': (
                    'fn app() -> Router { Router::new().route("/real", get(f)) }\n'
                    '#[cfg(test)]\nmod tests {\n    fn m() -> Router { Router::new().route("/fake3", get(f)) }\n}\n'
                    '#[tokio::test]\nasync fn t() { let r = Router::new().route("/fake4", get(f)); }\n'
                ),
                'src/inner.rs': '#![cfg(test)]\nfn m() -> Router { Router::new().route("/fake5", get(f)) }\n',
            }
        ).routes()
        self.assertEqual(sorted(found), [('GET', '/real')])

    def test_test_calls(self):
        found = RustRepo(
            {
                'src/a.rs': '#[test]\nfn t() { client.get("http://localhost/a"); }\nfn p() { client.get("/b"); }\n',
                'tests/it.rs': 'fn t() { client.get("/c"); }\n',
            }
        ).calls()
        self.assertTrue(found[('GET', '/a')].test)
        self.assertFalse(found[('GET', '/b')].test)
        self.assertTrue(found[('GET', '/c')].test)
        self.assertEqual(found[('GET', '/b')].function, 'p')


if __name__ == '__main__':
    unittest.main()
