import time
import unittest

from .support import RustRepo

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
        self.found = RustRepo(
            {
                'src/endpoints/mod.rs': AXUM_MOD,
                'src/endpoints/store.rs': AXUM_STORE,
                'src/endpoints/integrations/otlp.rs': AXUM_OTLP,
                'src/services/upload.rs': UPLOAD_CONST,
            }
        ).routes()

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
        all_routes = RustRepo({'src/endpoints/mod.rs': AXUM_MOD, 'src/endpoints/store.rs': AXUM_STORE}).extract()
        lives = [r for r in all_routes.routes if str(r.path) == '/api/0/relays/live']
        self.assertEqual(len(lives), 1)


class MethodRouterTest(unittest.TestCase):
    def test_chained_method_router_handlers(self):
        source = (
            'fn app() -> Router {\n'
            '    Router::new().route("/p", get(proxy).head(proxy).post(upload).on(MethodFilter::PUT, put))\n'
            '}\n'
        )
        found = sorted((sorted(r.methods), r.handler) for r in RustRepo({'src/app.rs': source}).extract().routes)
        self.assertEqual(found, [(['GET', 'HEAD'], 'proxy'), (['POST'], 'upload'), (['PUT'], 'put')])

    def test_layered_factory_deep_in_let_chain(self):
        lets = ''.join(f'    let r = r.route_layer(l{i});\n' for i in range(10))
        found = RustRepo(
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
        ).routes()
        self.assertEqual(sorted(found), [('POST', '/m')])
        self.assertEqual(found[('POST', '/m')].handler, 'minidump::handle')

    def test_service_suffixed_and_filtered_method_routers(self):
        source = (
            'use axum::routing::{get_service, on};\n'
            'fn app() -> Router {\n'
            '    Router::new()\n'
            '        .route("/files", get_service(ServeDir::new("x")))\n'
            '        .route("/both", on(MethodFilter::POST.or(MethodFilter::GET), both))\n'
            '        .route("/m", empty())\n'
            '}\n'
            'fn empty() -> MethodRouter { let x = 1; }\n'
        )
        found = RustRepo({'src/app.rs': source}).routes()
        self.assertEqual(found[('GET', '/files')].handler, 'ServeDir::new("x")')
        self.assertEqual(found[('GET', '/both')].methods, {'GET', 'POST'})
        self.assertEqual(found[('ANY', '/m')].handler, 'empty')


class RouterRootsTest(unittest.TestCase):
    def test_trailing_slash_variants_are_one_route(self):
        source = (
            'fn app() -> Router {\n'
            '    Router::new()\n'
            '        .route("/api/{project_id}/minidump", post(minidump))\n'
            '        .route("/api/{project_id}/minidump/", post(minidump))\n'
            '        .route("/other", post(minidump))\n'
            '}\n'
        )
        found = [(str(r.path), r.line) for r in RustRepo({'src/app.rs': source}).extract().routes]
        self.assertEqual(found, [('/api/{project_id}/minidump', 3), ('/other', 5)])

    def test_route_reachable_from_two_roots_keeps_the_first_found(self):
        source = (
            'fn all() -> Router {\n'
            '    raw().merge(internal())\n'
            '}\n'
            'fn public() -> Router { raw().route("/nf", any(nf)) }\n'
            'fn internal() -> Router { Router::new().route("/nf", any(nf)) }\n'
            'fn raw() -> Router { Router::new().route("/a", get(a)) }\n'
        )
        # all() is evaluated first and finds /nf through internal() (line 5); public()'s /nf (line 4) is the same route.
        found = RustRepo({'src/app.rs': source}).extract().routes
        self.assertEqual([(str(r.path), r.line) for r in found], [('/a', 6), ('/nf', 5)])

    def test_chains_on_one_let_bound_router_share_its_steps(self):
        # The legacy evaluator's quirk, kept: both chains extend the router `base` evaluates to, so the second
        # nest also serves the first chain's /b.
        source = (
            'fn app() {\n'
            '    let base = Router::new().route("/a", get(a));\n'
            '    serve(Router::new().nest("/v1", base.route("/b", get(b))));\n'
            '    serve(Router::new().nest("/v2", base.route("/c", get(c))));\n'
            '}\n'
        )
        found = RustRepo({'src/app.rs': source}).extract().routes
        self.assertEqual(
            [(str(r.path), r.line) for r in found],
            [('/v1/a', 2), ('/v1/b', 3), ('/v2/a', 2), ('/v2/b', 3), ('/v2/c', 4)],
        )

    def test_long_router_chain_is_linear(self):
        source = 'fn app() -> Router {\n    Router::new()\n'
        source += ''.join(f'        .route("/r{i}", get(h{i}))\n' for i in range(1500)) + '}\n'
        start = time.perf_counter()
        found = RustRepo({'src/app.rs': source}).extract().routes
        self.assertEqual(len(found), 1500)
        self.assertLess(time.perf_counter() - start, 5)

    def test_framework_from_use_declarations(self):
        found = RustRepo(
            {'src/a.rs': '// ported from actix-web\nfn app() -> Router { Router::new().route("/x", get(h)) }\n'}
        ).routes()
        self.assertEqual(found[('GET', '/x')].framework, 'axum')

    def test_non_router_files_and_unresolved_paths(self):
        found = RustRepo(
            {
                'src/other.rs': 'fn f() { rate_limits.merge(other); x.route("/nope", get(f)); }\n',
                'src/app.rs': 'fn app() -> Router { Router::new().route(&format!("/{}", x), get(f)).route(P, get(g)) }',
            }
        ).routes()
        self.assertEqual(found, {})


if __name__ == '__main__':
    unittest.main()
