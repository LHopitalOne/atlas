import os
import tempfile
import time
import unittest

from atlas_bridge.adapters.treesitter import rust


def run(files, repo='svc'):
    """Write {path: source} to a temporary repository and extract from every file."""
    with tempfile.TemporaryDirectory() as root:
        for path, source in files.items():
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w') as f:
                f.write(source)
        return rust.extract(repo, root, sorted(files) + ['missing.rs'])


def routes(files):
    return {(m, str(r.path)): r for r in run(files).routes for m in r.methods}


def calls(files):
    if isinstance(files, str):
        files = {'src/client.rs': files}
    return {(c.method, str(c.path)): c for c in run(files).calls}


AXUM_MOD = """
use axum::routing::{Router, any, get, post, MethodFilter, on};
use crate::services::upload::UPLOAD_PATH;

mod store;
mod integrations;

pub fn all_routes(config: &Config) -> Router<State> {
    public_routes(config).merge(internal_routes(config))
}

fn internal_routes(_: &Config) -> Router<State> {
    Router::new()
        .route("/api/relay/healthcheck/{kind}/", get(health_check::handle))
        .route("/api/relay/{*not_found}", any(statics::not_found))
}

fn public_routes(config: &Config) -> Router<State> {
    let web_routes = Router::new()
        .route("/api/0/relays/live/", get(health::live))
        .route("/proxy/{*path}", get(proxy).head(proxy))
        .route_layer(DefaultBodyLimit::max(10));
    let store_routes = Router::new()
        .route("/api/store/", store::route(config))
        .route("/api/{project_id}/cron/", on(MethodFilter::GET.or(MethodFilter::POST), monitor))
        .route(UPLOAD_PATH, store::route_head())
        .route("/legacy/:id/*rest", axum::routing::delete(legacy))
        .route("/unknown/", unknown::factory(config));
    let store_routes = store_routes.route("/api/{project_id}/extra/", post(extra));
    let integrations = match config.mode() {
        Mode::Managed => Router::new()
            .nest("/api/{project_id}/integration/otlp", integrations::otlp::routes(config)),
        Mode::Proxy => Router::new(),
    };
    Router::new()
        .merge(web_routes)
        .merge(store_routes)
        .merge(integrations)
        .route_service("/svc", tower_service)
        .nest_service("/static", ServeDir::new("assets"))
        .fallback(forward::forward)
}
"""

AXUM_STORE = """
use axum::routing::{MethodRouter, post, head as axum_head};

pub fn route(config: &Config) -> MethodRouter<State> {
    (post(handle_post).get(handle_get)).route_layer(DefaultBodyLimit::max(config.max()))
}

pub fn route_head() -> MethodRouter<State> {
    axum_head(handle_head).route_layer(layer())
}
"""

AXUM_OTLP = """
pub fn routes(config: &Config) -> axum::Router<State> {
    axum::Router::new()
        .route("/v1/traces", traces::route(config))
        .route("/v1/logs/", logs::route(config))
}

mod traces {
    pub fn route(config: &Config) -> MethodRouter<State> {
        post(handle).route_layer(limit())
    }
}

mod logs {
    pub fn route(config: &Config) -> MethodRouter<State> {
        if config.enabled() {
            return put(handle);
        }
        post(handle)
    }
}
"""

UPLOAD_CONST = 'pub const UPLOAD_PATH: &str = "/api/{project_id}/upload/{key}/";\n'


class AxumTest(unittest.TestCase):
    def setUp(self):
        self.found = routes(
            {
                'src/endpoints/mod.rs': AXUM_MOD,
                'src/endpoints/store.rs': AXUM_STORE,
                'src/endpoints/integrations/otlp.rs': AXUM_OTLP,
                'src/services/upload.rs': UPLOAD_CONST,
            }
        )

    def test_inline_method_routers(self):
        live = self.found[('GET', '/api/0/relays/live')]
        self.assertEqual(
            (live.file, live.line, live.handler, live.framework), ('src/endpoints/mod.rs', 20, 'health::live', 'axum')
        )
        self.assertIn(('GET', '/proxy/{*path}'), self.found)
        self.assertIn(('HEAD', '/proxy/{*path}'), self.found)
        self.assertIn(('ANY', '/api/relay/{*not_found}'), self.found)
        self.assertIn(('GET', '/api/relay/healthcheck/{kind}'), self.found)
        self.assertIn(('GET', '/api/{project_id}/cron'), self.found)
        self.assertIn(('POST', '/api/{project_id}/cron'), self.found)
        self.assertIn(('DELETE', '/legacy/{id}/{*rest}'), self.found)
        self.assertIn(('POST', '/api/{project_id}/extra'), self.found)

    def test_factories_resolved_in_other_modules(self):
        store = self.found[('POST', '/api/store')]
        self.assertEqual((store.handler, store.methods), ('store::handle_post', {'POST'}))
        self.assertEqual(self.found[('GET', '/api/store')].handler, 'store::handle_get')
        head = self.found[('HEAD', '/api/{project_id}/upload/{key}')]
        self.assertEqual(head.handler, 'store::handle_head')
        self.assertEqual(self.found[('ANY', '/unknown')].handler, 'unknown::factory')

    def test_nest_prefixes_and_services(self):
        traces = self.found[('POST', '/api/{project_id}/integration/otlp/v1/traces')]
        self.assertEqual((traces.file, traces.handler), ('src/endpoints/integrations/otlp.rs', 'traces::handle'))
        self.assertIn(('PUT', '/api/{project_id}/integration/otlp/v1/logs'), self.found)
        self.assertIn(('POST', '/api/{project_id}/integration/otlp/v1/logs'), self.found)
        self.assertNotIn(('POST', '/v1/traces'), self.found)  # only mounted under the prefix
        self.assertIn(('ANY', '/svc'), self.found)
        self.assertIn(('ANY', '/static/{*rest}'), self.found)

    def test_each_route_once(self):
        all_routes = run({'src/endpoints/mod.rs': AXUM_MOD, 'src/endpoints/store.rs': AXUM_STORE}).routes
        lives = [r for r in all_routes if str(r.path) == '/api/0/relays/live']
        self.assertEqual(len(lives), 1)

    def test_trailing_slash_variants_are_one_route(self):
        source = (
            'fn app() -> Router {\n'
            '    Router::new()\n'
            '        .route("/api/{project_id}/minidump", post(minidump))\n'
            '        .route("/api/{project_id}/minidump/", post(minidump))\n'
            '        .route("/other", post(minidump))\n'
            '}\n'
        )
        found = [(str(r.path), r.line) for r in run({'src/app.rs': source}).routes]
        self.assertEqual(found, [('/api/{project_id}/minidump', 3), ('/other', 5)])

    def test_chained_method_router_handlers(self):
        source = (
            'fn app() -> Router {\n'
            '    Router::new().route("/p", get(proxy).head(proxy).post(upload).on(MethodFilter::PUT, put))\n'
            '}\n'
        )
        found = sorted((sorted(r.methods), r.handler) for r in run({'src/app.rs': source}).routes)
        self.assertEqual(found, [(['GET', 'HEAD'], 'proxy'), (['POST'], 'upload'), (['PUT'], 'put')])

    def test_layered_factory_deep_in_let_chain(self):
        lets = ''.join(f'    let r = r.route_layer(l{i});\n' for i in range(10))
        found = routes(
            {
                'src/app.rs': (
                    'fn app() -> Router {\n'
                    '    let r = Router::new().route("/m", minidump::route(config));\n'
                    f'{lets}'
                    '    Router::new().merge(r)\n'
                    '}\n'
                ),
                'src/minidump.rs': 'pub fn route(c: &C) -> MethodRouter {\n    post(handle)'
                + '.route_layer(x)' * 12
                + '\n}\n',
            }
        )
        self.assertEqual(sorted(found), [('POST', '/m')])
        self.assertEqual(found[('POST', '/m')].handler, 'minidump::handle')

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
        self.assertEqual(sorted(routes({'src/local.rs': source})), [('GET', '/real')])

    def test_long_router_chain_is_linear(self):
        source = 'fn app() -> Router {\n    Router::new()\n'
        source += ''.join(f'        .route("/r{i}", get(h{i}))\n' for i in range(1500)) + '}\n'
        start = time.perf_counter()
        found = run({'src/app.rs': source}).routes
        self.assertEqual(len(found), 1500)
        self.assertLess(time.perf_counter() - start, 5)

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
        found = run({'src/a.rs': source})
        self.assertEqual([str(r.path) for r in found.routes], ['/real'])
        tests = {str(c.path): c.test for c in found.calls}
        self.assertEqual(tests, {'/a': True, '/b': True, '/c': True, '/d': True, '/e': False, '/f': False})

    def test_framework_from_use_declarations(self):
        found = routes(
            {'src/a.rs': '// ported from actix-web\nfn app() -> Router { Router::new().route("/x", get(h)) }\n'}
        )
        self.assertEqual(found[('GET', '/x')].framework, 'axum')

    def test_test_routers_skipped(self):
        found = routes(
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
        )
        self.assertEqual(sorted(found), [('GET', '/real')])

    def test_non_router_files_and_unresolved_paths(self):
        found = routes(
            {
                'src/other.rs': 'fn f() { rate_limits.merge(other); x.route("/nope", get(f)); }\n',
                'src/app.rs': 'fn app() -> Router { Router::new().route(&format!("/{}", x), get(f)).route(P, get(g)) }',
            }
        )
        self.assertEqual(found, {})


ACTIX = """
use actix_web::{web, App, HttpServer, get, post};

#[get("/hello/{name}")]
async fn hello(name: web::Path<String>) -> String { name.into_inner() }

#[post("/items")]
async fn create() -> HttpResponse { HttpResponse::Ok().finish() }

#[actix_web::route("/multi", method = "GET", method = "HEAD")]
async fn multi() -> HttpResponse { HttpResponse::Ok().finish() }

fn config(cfg: &mut web::ServiceConfig) {
    cfg.service(web::resource("/configured").route(web::put().to(put_handler)));
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .service(hello)
            .service(
                web::scope("/api")
                    .service(create)
                    .service(web::resource("/users/{id:\\\\d+}").route(web::post().to(add_user)).get(get_user))
                    .route("/ping", web::get().to(ping))
                    .service(web::resource("/any").to(anything)),
            )
            .configure(config)
    })
    .bind(("127.0.0.1", 8080))?
    .run()
    .await
}

#[cfg(test)]
mod tests {
    #[get("/test-only")]
    async fn fake() -> String { String::new() }
}
"""


class ActixTest(unittest.TestCase):
    def test_actix_routes(self):
        found = routes({'src/main.rs': ACTIX})
        self.assertEqual(
            sorted(found),
            [
                ('ANY', '/api/any'),
                ('GET', '/api/ping'),
                ('GET', '/api/users/{id}'),
                ('GET', '/hello/{name}'),
                ('GET', '/multi'),
                ('HEAD', '/multi'),
                ('POST', '/api/items'),
                ('POST', '/api/users/{id}'),
                ('PUT', '/configured'),
            ],
        )
        hello = found[('GET', '/hello/{name}')]
        self.assertEqual((hello.handler, hello.framework, hello.line), ('hello', 'actix', 4))
        self.assertEqual(found[('POST', '/api/users/{id}')].handler, 'add_user')
        self.assertEqual(found[('GET', '/api/ping')].handler, 'ping')

    def test_unmounted_attribute_route(self):
        source = 'use actix_web::get;\n#[get("/alone")]\n// doc\nasync fn alone() {}\n#[get("rel")]\nfn r() {}\n'
        found = routes({'src/h.rs': source})
        self.assertEqual(sorted(found), [('GET', '/alone')])

    def test_raw_string_attribute_route(self):
        source = 'use actix_web::get;\n#[get(r"/raw")]\nasync fn e() {}\n#[get(r#"/hash"#)]\nasync fn h() {}\n'
        found = routes({'src/h.rs': source})
        self.assertEqual(sorted(found), [('GET', '/hash'), ('GET', '/raw')])
        self.assertEqual(found[('GET', '/raw')].framework, 'actix')


REQUESTS = """
use std::borrow::Cow;

impl UpstreamQuery for GetProjectStates {
    type Response = Resp;

    fn method(&self) -> Method {
        Method::POST
    }

    fn path(&self) -> Cow<'static, str> {
        Cow::Borrowed("/api/0/relays/projectconfigs/?version=3")
    }
}

impl UpstreamRequest for SendEnvelope {
    fn method(&self) -> reqwest::Method {
        reqwest::Method::POST
    }

    fn path(&self) -> Cow<'_, str> {
        format!("/api/{}/envelope/", self.envelope.scoping().project_id).into()
    }
}

impl UpstreamRequest for GetHealthCheck {
    fn method(&self) -> Method { Method::GET }
    fn path(&self) -> Cow<'_, str> { "/api/0/relays/live/".into() }
}

impl UpstreamRequest for UploadRequest {
    fn method(&self) -> Method {
        match self.kind {
            Kind::Create { .. } => Method::POST,
            Kind::Upload { .. } => Method::PATCH,
        }
    }

    fn path(&self) -> Cow<'_, str> {
        let project_id = self.project_id;
        match &self.kind {
            Kind::Create { id, .. } => Cow::Owned(format!("/api/{project_id}/upload/")),
            Kind::Upload { uri } => Cow::Borrowed(uri),
        }
    }
}

impl Endpoint for Thing<T> {
    fn url(&self) -> String {
        String::from(THING_PATH)
    }
}

impl Display for Other {
    fn fmt(&self) -> String { "/not/a/request".into() }
}

const THING_PATH: &str = "/things/";

#[cfg(test)]
mod tests {
    impl UpstreamRequest for Fake {
        fn path(&self) -> Cow<'_, str> { "/fake/".into() }
    }
}
"""


class RequestTraitTest(unittest.TestCase):
    def setUp(self):
        self.found = calls({'src/services/upstream.rs': REQUESTS})

    def test_paths_and_methods(self):
        self.assertEqual(
            sorted(self.found),
            [
                ('ANY', '/fake'),
                ('ANY', '/things'),
                ('GET', '/api/0/relays/live'),
                ('POST', '/api/0/relays/projectconfigs'),
                ('POST', '/api/{project_id}/envelope'),
                ('POST', '/api/{project_id}/upload'),  # the method of the matching arm of `fn method`
            ],
        )
        c = self.found[('POST', '/api/0/relays/projectconfigs')]
        self.assertEqual((c.line, c.function, c.test), (12, 'GetProjectStates::path', False))
        self.assertTrue({'UpstreamQuery', 'Upstream Query', 'GetProjectStates', 'src/services/upstream.rs'} <= c.hints)
        self.assertEqual(self.found[('ANY', '/things')].function, 'Thing::url')
        self.assertTrue(self.found[('ANY', '/fake')].test)

    def test_nested_generics_stripped(self):
        found = calls(
            'impl UpstreamRequest<Vec<u8>> for Foo<Option<T>> {\n'
            '    fn method(&self) -> Method { Method::POST }\n'
            '    fn path(&self) -> Cow<str> { "/api/x/".into() }\n'
            '}\n'
        )
        c = found[('POST', '/api/x')]
        self.assertEqual(c.function, 'Foo::path')
        self.assertTrue({'Foo', 'UpstreamRequest'} <= c.hints)


class ClientTest(unittest.TestCase):
    def test_reqwest_verbs(self):
        found = calls(
            """
static CLIENT: Lazy<Client> = Lazy::new(|| connection_from_url(settings.SNUBA_URL));

impl Symbolicator {
    async fn symbolicate(&self, id: u32, base: &str) {
        let url = format!("{}/symbolicate/{}", base, id);
        self.client.post(&url).send().await?;
        CLIENT.get("http://snuba:1218/health").send().await?;
        let client = reqwest::Client::builder().build().unwrap();
        client.delete(format!("{base_url}/items/{:?}?force=1", id)).send();
        self.http.put(format!("{0}/a/{{literal}}/{1}", base, id));
    }
}
"""
        )
        self.assertEqual(
            sorted(found),
            [('DELETE', '/items/{id}'), ('GET', '/health'), ('POST', '/symbolicate/{id}'), ('PUT', '/a/literal/{id}')],
        )
        post = found[('POST', '/symbolicate/{id}')]
        self.assertEqual((post.line, post.function, post.test), (7, 'Symbolicator::symbolicate', False))
        self.assertTrue({'base', 'self.client', 'Symbolicator', 'symbolicate', 'src/client.rs', 'send'} <= post.hints)
        health = found[('GET', '/health')]
        self.assertTrue({'snuba', 'CLIENT', 'Lazy::new(|| connection_from_url(settings.SNUBA_URL))'} <= health.hints)
        delete = found[('DELETE', '/items/{id}')]
        self.assertTrue({'base_url', 'reqwest::Client::builder().build().unwrap()'} <= delete.hints)

    def test_method_first_calls_and_join(self):
        found = calls(
            """
fn send(client: &Client, base: Url, id: u64) {
    let req = Request::new(Method::POST, "/v1/upload");
    client.request(Method::PUT, base.join("files/").unwrap());
    let api = base.join("/api/0/").unwrap();
    let url = api.join(&format!("projects/{id}/events/")).unwrap();
    client.get(url.clone());
    ForwardRequest::builder(Method::POST, "/api/0/relays/register/").send_to(state.upstream_relay());
    reqwest::get("https://example.com/x/y");
    client.patch(BASE.to_string() + "/patch/" + &id.to_string());
    client.request(method, url);
}
"""
        )
        self.assertEqual(
            sorted(found),
            [
                ('ANY', '/api/0/projects/{id}/events'),
                ('GET', '/api/0/projects/{id}/events'),
                ('GET', '/x/y'),
                ('PATCH', '/patch/{id}'),
                ('POST', '/api/0/relays/register'),
                ('POST', '/v1/upload'),
                ('PUT', '/files'),
            ],
        )
        fwd = found[('POST', '/api/0/relays/register')]
        self.assertTrue({'ForwardRequest::builder', 'send_to', 'upstream_relay'} <= fwd.hints)
        self.assertIn('example.com', found[('GET', '/x/y')].hints)
        self.assertIn('BASE.to_string()', found[('PATCH', '/patch/{id}')].hints)

    def test_rejects_non_requests(self):
        found = calls(
            """
fn f(request: &Request, map: &HashMap<String, String>) {
    request.headers().get("x-forwarded-for");
    map.get("key");
    cache.get(&key);
    client.get(url);
    client.get("  ");
    self.client.get(build_url());
    client.get(some.method("x"));
    other::post("/x");
    Self::get("/y");
    client.get("relative");
}
"""
        )
        self.assertEqual(sorted(found), [('GET', '/relative')])

    def test_test_code(self):
        found = calls(
            {
                'src/a.rs': '#[test]\nfn t() { client.get("http://localhost/a"); }\nfn p() { client.get("/b"); }\n',
                'tests/it.rs': 'fn t() { client.get("/c"); }\n',
            }
        )
        self.assertTrue(found[('GET', '/a')].test)
        self.assertFalse(found[('GET', '/b')].test)
        self.assertTrue(found[('GET', '/c')].test)
        self.assertEqual(found[('GET', '/b')].function, 'p')


class RobustnessTest(unittest.TestCase):
    def test_cycles_terminate(self):
        found = run(
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
        )
        self.assertEqual(sorted((str(r.path), r.handler) for r in found.routes), [('/x', 'm'), ('/y', 'me')])
        self.assertEqual(found.calls, [])

    def test_malformed_files(self):
        with tempfile.TemporaryDirectory() as root:
            files = {
                'empty.rs': b'',
                'bytes.rs': b'fn f() { client.get("/a\xff/b"); }\n'
                b'fn r() -> Router { Router::new().route("/x", get(h)) }',
                'broken.rs': b'}}}{{{ fn ( Router .route( "/x" , get( ',
                'digit.rs': 'fn f() { client.get(format!("/a/{\u00b2}/{}", x, y)); }'.encode(),
            }
            for name, data in files.items():
                with open(os.path.join(root, name), 'wb') as f:
                    f.write(data)
            found = rust.extract('svc', root, sorted(files))
        self.assertEqual([str(r.path) for r in found.routes], ['/x'])
        self.assertEqual(sorted(str(c.path) for c in found.calls), ['/a/{param}/{x}', '/a\ufffd/b'])

    def test_deep_nesting(self):
        n = 1500
        found = calls(
            {
                'src/concat.rs': 'fn f() { client.get("/a"' + ' + "/b"' * n + '); }\n',
                'src/elseif.rs': 'fn g() { client.post(if a { "/c" }'
                + ' else if b { "/d" }' * n
                + ' else { "/e" }); }\n',
                'src/blocks.rs': 'fn h() { client.put(' + '{ ' * n + '"/f"' + ' }' * n + '); }\n',
                'src/pass.rs': 'fn k() { client.patch("/g"' + '.to_string()' * n + '); }\n',
                'src/use.rs': 'use ' + 'a::{' * n + 'b' + '}' * n + ';\n',
            }
        )
        self.assertEqual(found[('GET', '/a' + '/b' * n)].line, 1)
        self.assertIn(('POST', '/c'), found)
        self.assertIn(('PUT', '/f'), found)
        self.assertEqual(sorted(found), [('GET', '/a' + '/b' * n), ('POST', '/c'), ('PUT', '/f')])

    def test_many_lookups_in_one_function(self):
        source = 'fn f() {\n' + ''.join(f'    let k{i} = x;\n    m.get(k{i});\n' for i in range(2000)) + '}\n'
        start = time.perf_counter()
        self.assertEqual(calls(source), {})
        self.assertLess(time.perf_counter() - start, 5)


class HelpersTest(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(rust._canonical('/a/:id/*rest'), '/a/{id}/{*rest}')
        self.assertEqual(rust._canonical('/a/{id:\\d+}/{tail}*'), '/a/{id}/{*tail}')
        self.assertEqual(rust._join('/api/', '/'), '/api')
        self.assertEqual(rust._join('/', '/x'), '/x')


if __name__ == '__main__':
    unittest.main()
