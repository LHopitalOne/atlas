import os
import tempfile
import textwrap
import unittest
from unittest import mock

from atlas_bridge.adapters.treesitter import python
from atlas_bridge.core.http import ANY


def extract(files, repo='svc'):
    with tempfile.TemporaryDirectory() as d:
        for path, src in files.items():
            full = os.path.join(d, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write(textwrap.dedent(src))
        return python.extract(repo, d, sorted(files) + ['missing.py'])


def routes(ex):
    return {(str(r.path), tuple(sorted(r.methods))) for r in ex.routes}


def requests_(ex, test=False):
    return {(c.method, str(c.path)) for c in ex.calls if c.kind == 'request' and c.test == test}


def call(ex, path):
    return next(c for c in ex.calls if str(c.path) == path)


class RegexTemplateTest(unittest.TestCase):
    def test_named_groups_anchors_and_optional_tails(self):
        t = python._regex_templates
        self.assertEqual(t(r'^(?P<org>[^/]+)/(?P<proj>[^/]+)/files/dsyms/$'), ['{org}/{proj}/files/dsyms/'])
        self.assertEqual(t(r'^api/client-config/?$'), ['api/client-config'])
        self.assertEqual(t(r'^api/relay/.*$'), ['api/relay/{*path}'])
        self.assertEqual(t(r'^(?:issues|groups)/'), ['issues/', 'groups/'])
        self.assertEqual(t(r'^robots\.txt$'), ['robots.txt'])
        self.assertEqual(t(r'^(?P<path>.*)$'), ['{*path}'])
        self.assertEqual(t(r'^(\d+)/x(?:/extra)?/$'), ['{param}/x/'])
        self.assertEqual(t(r'^v\d+/[a-z]+/(?=x)(?i)y\b$'), ['v{param}/{param}/y'])
        self.assertEqual(t(r'^(?P<id>(?:a|\d+))/(?P=id)/\w*/z{1,2}/e?$'), ['{id}/{param}/{param}/z/'])
        self.assertEqual(t(r'^a|b$'), ['a', 'b'])
        self.assertEqual(t(r'^[]x]/[^]]/(a'), ['{param}/{param}/{param}'])

    def test_flask_converters(self):
        self.assertEqual(python._flask_path('/a/<int:id>/<path:rest>/<name>'), '/a/{id}/{*rest}/{name}')
        self.assertEqual(python._flask_path('/f/{p:path}/{n:int}'), '/f/{*p}/{n}')


class DecoratorRouteTest(unittest.TestCase):
    def test_flask_app_and_blueprints(self):
        ex = extract(
            {
                'app/views.py': """
                from flask import Flask, Blueprint
                application = Flask(__name__)
                bp = Blueprint('bp', __name__, url_prefix='/bp')

                @application.route('/rpc/<name>/<version>', methods=['POST'])
                def rpc(name, version):
                    pass

                @application.route('/<dataset:dataset>/snql', methods=['GET', 'POST'])
                @other.decorator
                def snql(dataset):
                    pass

                @application.route('/health')
                def health():
                    pass

                @bp.get('/items/<int:item_id>')
                def item(item_id):
                    pass

                @application.route('/dyn', methods=METHODS)
                def dyn():
                    pass

                @application.route('not a path')
                @application.cache.get('key')
                def nope():
                    pass

                @application.route
                def bare():
                    pass

                @decorator
                class C:
                    pass

                application.add_url_rule('/rule/<path:rest>', 'rule', view_func=rule_view, methods=['PUT'])
                application.add_url_rule(rule=None)
                """,
                'app/main.py': """
                from app.views import bp
                from app import views
                app.register_blueprint(bp, url_prefix='/v2')
                app.register_blueprint(views.unknown, url_prefix='/x')
                app.register_blueprint(bp)
                """,
            }
        )
        self.assertEqual(
            routes(ex),
            {
                ('/rpc/{name}/{version}', ('POST',)),
                ('/{dataset}/snql', ('GET', 'POST')),
                ('/health', ('GET',)),
                ('/v2/items/{item_id}', ('GET',)),
                ('/dyn', (ANY,)),
                ('/rule/{*rest}', ('PUT',)),
            },
        )
        r = next(r for r in ex.routes if str(r.path) == '/rpc/{name}/{version}')
        self.assertEqual((r.file, r.line, r.handler, r.framework), ('app/views.py', 6, 'rpc', 'flask'))
        self.assertEqual(next(r for r in ex.routes if str(r.path) == '/rule/{*rest}').handler, 'rule_view')

    def test_fastapi_routers(self):
        ex = extract(
            {
                'api/routes.py': """
                from fastapi import APIRouter, FastAPI
                router = APIRouter(prefix='/items')
                app = FastAPI()

                @router.get('/{item_id}')
                async def read(item_id):
                    pass

                @router.api_route('/files/{p:path}', methods=['GET', 'POST'])
                def files(p):
                    pass

                @app.post('/root')
                def root():
                    pass

                app.include_router(router, prefix='/api')
                """
            }
        )
        self.assertEqual(
            routes(ex),
            {('/api/items/{item_id}', ('GET',)), ('/api/items/files/{*p}', ('GET', 'POST')), ('/root', ('POST',))},
        )
        self.assertEqual({r.framework for r in ex.routes}, {'fastapi'})

    def test_empty_paths_name_the_prefix(self):
        ex = extract(
            {
                'api/items.py': """
                from fastapi import APIRouter
                router = APIRouter(prefix='/items')

                @router.get('')
                def list_items():
                    pass

                @router.post('/')
                def create():
                    pass
                """,
                'web/things.py': """
                from flask import Blueprint
                bp = Blueprint('things', __name__, url_prefix='/things')
                other = make()

                @bp.route('', methods=['GET'])
                def things():
                    pass

                @other.get('')
                def not_a_route():
                    pass
                """,
            }
        )
        self.assertEqual(routes(ex), {('/items', ('GET',)), ('/items', ('POST',)), ('/things', ('GET',))})

    def test_methods_lists(self):
        ex = extract(
            {
                'app.py': """
                from flask import Flask
                app = Flask(__name__)
                M = ['GET', 'post']

                @app.route('/named', methods=M)
                def named():
                    pass

                @app.route('/mixed', methods=['GET', verb])
                def mixed():
                    pass

                @app.route('/call', methods=allowed())
                def call():
                    pass
                """
            }
        )
        self.assertEqual(routes(ex), {('/named', ('GET', 'POST')), ('/mixed', (ANY,)), ('/call', (ANY,))})


DJANGO = {
    'proj/settings.py': """
    ROOT_URLCONF = 'proj.urls'
    """,
    'proj/tests/settings.py': """
    ROOT_URLCONF = 'proj.test_urls'
    """,
    'proj/urls.py': """
    from django.urls import include, path, re_path
    from proj.api.urls import urlpatterns as api_patterns

    urlpatterns = [
        re_path(r'^api/0/', include('proj.api.urls')),
        path('v2/', include(api_patterns)),
        re_path(r'^ext/', include([re_path(r'^gh/', include('proj.ext.urls'))])),
        re_path(r'^loop/', include('proj.urls')),
        re_path(r'^gone/', include('nowhere.urls')),
        re_path(r'^none/', include()),
        url(r'^old/(?P<id>\\d+)/$', views.old, name='old'),
    ]
    urlpatterns += [path('extra/<int:pk>/', views.extra)]
    urlpatterns.append(path('appended/', views.appended))
    urlpatterns.extend([path('extended/', views.extended)])
    urlpatterns.insert(0, path('inserted/', views.inserted))
    if DEBUG:
        urlpatterns += patterns('', url(r'^debug/$', views.debug))
    """,
    'proj/api/urls.py': """
    from django.urls import include, re_path
    from proj.api.endpoints import RelayHealthCheck, RelayRegister
    from proj.api import shared
    from .more import MORE_URLS

    def make_urls(name_prefix, legacy=False):
        details = [re_path(r'^(?P<issue_id>[^/]+)/$', GroupDetails.as_view(), name=f'{name_prefix}-details')]
        return details + [re_path(r'^(?P<issue_id>[^/]+)/notes/$', Notes.as_view(), name=f'{name_prefix}-notes')]

    RELAY_URLS = [
        re_path(r'^register/challenge/$', RelayRegister.as_view(), name='relay-register'),
        re_path(r'^live/$', RelayHealthCheck.as_view(), name='relays-healthcheck'),
    ]
    PROJECT_URLS = (
        re_path(
            r'^(?P<organization_id_or_slug>[^/]+)/(?P<project_id_or_slug>[^/]+)/files/dsyms/$',
            csrf_exempt(DebugFilesEndpoint.as_view()),
            name='dsym-files',
        ),
    )
    urlpatterns = [
        re_path(r'^relays/', include(RELAY_URLS)),
        re_path(r'^projects/', include((PROJECT_URLS, 'projects'), namespace='p')),
        re_path(r'^(?:issues|groups)/', include(make_urls('api-0', legacy=True))),
        re_path(r'^shared/', include(shared.SHARED_URLS)),
        re_path(r'^more/', include(MORE_URLS + [re_path(r'^tail/$', views.tail)])),
        re_path(r'^var/', include(list(VARIANTS))),
        re_path(PATTERN, views.dynamic),
        *shared.SPLAT_URLS,
    ]
    VARIANTS = [re_path(r'^v/$', views.v)]
    PATTERN = r'^dyn/$'
    """,
    'proj/api/shared.py': """
    SHARED_URLS = [re_path(r'^one/$', views.one)]
    SPLAT_URLS = [re_path(r'^splat/$', views.splat)]
    """,
    'proj/api/more.py': """
    MORE_URLS = [re_path(r'^m/$', views.m)]
    """,
    'proj/api/endpoints/__init__.py': """
    from .relay import RelayHealthCheck, RelayRegister
    """,
    'proj/api/endpoints/relay.py': """
    class Endpoint:
        def options(self, request):
            pass

    class RelayHealthCheck(Endpoint):
        def get(self, request):
            pass

    class RelayRegister(Endpoint):
        @decorated
        def post(self, request):
            pass

        x = 1
    """,
    'proj/api/endpoints/debug.py': """
    class Base:
        def get(self, request):
            pass

        def delete(self, request):
            pass

    class DebugFilesEndpoint(Base):
        pass

    class Notes(Missing, mod.Other):
        pass
    """,
    'proj/ext/urls.py': """
    urlpatterns = [re_path(r'^webhook/$', Webhook.as_view())]
    """,
}


class DjangoRouteTest(unittest.TestCase):
    def test_includes_compose_from_root_urlconf(self):
        ex = extract(DJANGO)
        got = {str(r.path): r for r in ex.routes}
        live = got['/api/0/relays/live']
        self.assertEqual(
            (live.methods, live.handler, live.name), (frozenset({'GET'}), 'RelayHealthCheck', 'relays-healthcheck')
        )
        self.assertEqual((live.file, live.framework), ('proj/api/urls.py', 'django'))
        self.assertEqual(got['/api/0/relays/register/challenge'].methods, frozenset({'POST'}))
        dsyms = got['/api/0/projects/{organization_id_or_slug}/{project_id_or_slug}/files/dsyms']
        self.assertEqual((dsyms.name, dsyms.methods), ('dsym-files', frozenset({'GET', 'DELETE'})))
        self.assertEqual(got['/api/0/issues/{issue_id}'].name, 'api-0-details')
        self.assertEqual(got['/api/0/groups/{issue_id}/notes'].methods, frozenset({ANY}))
        for p in (
            '/v2/relays/live',
            '/ext/gh/webhook',
            '/api/0/shared/one',
            '/api/0/splat',
            '/api/0/more/m',
            '/api/0/more/tail',
            '/api/0/var/v',
            '/api/0/dyn',
            '/old/{id}',
            '/extra/{pk}',
            '/appended',
            '/extended',
            '/inserted',
            '/debug',
            '/loop/api/0/relays/live',
        ):
            self.assertIn(p, got)
        self.assertEqual(got['/extra/{pk}'].methods, frozenset({ANY}))
        self.assertEqual(got['/old/{id}'].handler, 'views.old')
        self.assertFalse(any(p.startswith('/gone') or p.startswith('/loop/loop') for p in got))

    def test_without_root_urlconf_every_unincluded_module_is_a_root(self):
        files = {k: v for k, v in DJANGO.items() if 'settings' not in k}
        files['other/urls.py'] = "urlpatterns = [re_path(r'^solo/$', views.solo)]\n"
        got = {str(r.path) for r in extract(files).routes}
        self.assertIn('/solo', got)
        self.assertIn('/api/0/relays/live', got)
        self.assertNotIn('/relays/live', got)
        self.assertNotIn('/webhook', got)

    def test_reassignment_that_reads_itself_keeps_earlier_entries(self):
        ex = extract(
            {
                'a/urls.py': """
                urlpatterns = [path('v/', V)]
                urlpatterns = urlpatterns + [path('w/', W)]
                urlpatterns = [*urlpatterns, path('x/', X)]
                """,
                'b/urls.py': """
                urlpatterns = [path('old/', Old)]
                urlpatterns = [path('new/', New)]
                """,
            }
        )
        self.assertEqual({str(r.path) for r in ex.routes}, {'/v', '/w', '/x', '/new'})


class RequestTest(unittest.TestCase):
    def test_pool_urlopen_and_module_client_hints(self):
        ex = extract(
            {
                'src/app/utils/snuba.py': """
                from django.conf import settings
                _snuba_pool = connection_from_url(settings.SENTRY_SNUBA, timeout=5)

                def raw_query(request):
                    return _snuba_pool.urlopen('POST', f'/{request.dataset}/snql', body=b'')

                def delete(query):
                    return _snuba_pool.urlopen('DELETE', f'/{query.storage_name}')
                """,
                'src/app/eventstream.py': """
                from app.utils import snuba
                from app.utils.snuba import _snuba_pool
                from app.consts import INSERT

                class Stream:
                    def send(self):
                        snuba._snuba_pool.urlopen('POST', INSERT)

                    def drop(self):
                        method = 'POST'
                        url = '/tests/drop'
                        _snuba_pool.urlopen(method=method, url=url)
                """,
                'src/app/consts.py': """
                INSERT = '/tests/entities/items/insert'
                """,
            }
        )
        self.assertEqual(
            requests_(ex),
            {
                ('POST', '/{dataset}/snql'),
                ('DELETE', '/{storage_name}'),
                ('POST', '/tests/entities/items/insert'),
                ('POST', '/tests/drop'),
            },
        )
        c = call(ex, '/{dataset}/snql')
        self.assertEqual((c.file, c.line, c.function), ('src/app/utils/snuba.py', 6, 'raw_query'))
        self.assertIn('connection_from_url(settings.SENTRY_SNUBA, timeout=5)', c.hints)
        self.assertIn('_snuba_pool', c.hints)
        insert = call(ex, '/tests/entities/items/insert')
        self.assertEqual(insert.function, 'Stream.send')
        self.assertIn('connection_from_url(settings.SENTRY_SNUBA, timeout=5)', insert.hints)
        self.assertIn('connection_from_url(settings.SENTRY_SNUBA, timeout=5)', call(ex, '/tests/drop').hints)

    def test_url_building_forms(self):
        ex = extract(
            {
                'svc/client.py': """
                import os
                import posixpath
                import requests
                from urllib.parse import urljoin
                from urllib.request import Request, urlopen
                from svc import consts

                BASE = 'http://orders:8000'
                ENDPOINT = '/tests/{entity}/insert'

                class Client:
                    path = '/class/attr'

                    def __init__(self):
                        self.session = requests.Session()

                    def a(self, entity):
                        requests.post(settings.SNUBA + '/tests/drop')
                        requests.post(settings.SNUBA + ENDPOINT.format(entity=entity))
                        requests.get('{}/api/{}/store/'.format(self.url, project_id))
                        requests.get('/p/%s/q/%(name)s' % (a, b))
                        requests.get('%s/pct' % base)
                        requests.get(urljoin(self.base_url, 'symbolicate'))
                        requests.get(os.path.join('/root', 'sub'))
                        requests.get(posixpath.join(base, 'joined'))
                        requests.get('/'.join(['', 'slash', name]))
                        requests.get(BASE + '/orders/' + order_id)
                        requests.get(f'{BASE}/fstr/{order_id}')
                        requests.put(consts.URL)
                        requests.get(self.path)
                        requests.delete(str(self.path) + '/x')
                        self.session.get(url='/kw', timeout=3)

                    def b(self, flag):
                        url = '/one' if flag else '/two'
                        url += '/more'
                        urlopen(Request(url, method='PUT'))
                        urlopen('/plain')
                        urlopen('/m', method='HEAD')
                        self.http.request('patch', f'/v{version}/items')
                        self.http.request(verb, '/unknown-method')
                        x = 3
                        requests.get(x + 1)
                """,
                'svc/consts.py': """
                URL = BASE + '/consts'
                BASE = 'http://x'
                """,
                'svc/more.py': """
                import requests
                API = 'http://svc'
                API = API + '/api'
                a0 = a1 = a2 = a3 = '/chained'

                def c(provider_url, n, addr):
                    requests.get(f'/zk/{n}/{{shard}}/t')
                    requests.get(f'{provider_url}ip/{addr}')
                    requests.get('/pct/%d%%' % n)
                    requests.get(API + '/users')
                    requests.get(a0)
                """,
            }
        )
        self.assertEqual(
            requests_(ex),
            {
                ('POST', '/tests/drop'),
                ('POST', '/tests/{entity}/insert'),
                ('GET', '/api/{project_id}/store'),
                ('GET', '/p/{param}/q/{name}'),
                ('GET', '/pct'),
                ('GET', '/symbolicate'),
                ('GET', '/root/sub'),
                ('GET', '/joined'),
                ('GET', '/slash/{name}'),
                ('GET', '/orders/{order_id}'),
                ('GET', '/fstr/{order_id}'),
                ('PUT', '/consts'),
                ('GET', '/class/attr'),
                ('DELETE', '/class/attr/x'),
                ('GET', '/kw'),
                ('PUT', '/one/more'),
                ('PUT', '/two/more'),
                (ANY, '/plain'),
                ('HEAD', '/m'),
                ('PATCH', '/v{version}/items'),
                (ANY, '/unknown-method'),
                ('GET', '/zk/{n}/{shard}/t'),
                ('GET', '/ip/{addr}'),
                ('GET', '/pct/{param}%'),
                ('GET', '/api/users'),
                ('GET', '/chained'),
            },
        )
        self.assertIn('provider_url', call(ex, '/ip/{addr}').hints)
        self.assertIn('svc', call(ex, '/api/users').hints)
        self.assertIn('settings.SNUBA', call(ex, '/tests/drop').hints)
        self.assertIn('orders', call(ex, '/orders/{order_id}').hints)
        self.assertIn('self.base_url', call(ex, '/symbolicate').hints)
        self.assertIn('requests.Session()', call(ex, '/kw').hints)

    def test_long_assignment_chain(self):
        chain = ' = '.join(f'a{i}' for i in range(3000))
        ex = extract({'svc/chain.py': f"{chain} = '/x'\ndef f():\n    requests.get(a2999)\n    requests.get(a0)\n"})
        self.assertEqual(requests_(ex), {('GET', '/x')})

    def test_noise_is_ignored(self):
        ex = extract(
            {
                'svc/misc.py': """
                def f(d, key, request):
                    d.get('key')
                    cache.get(key)
                    request.session.get('user_id')
                    options.get('a.b')
                    d.get(prefix + 'Error')
                    requests.get(url)
                    requests.get()
                    requests.get(*args)
                    session.request('GET')
                    obj.get('/real/path')
                    get('/bare')
                    requests.get('has space')
                    requests.get('/two/args', params)

                def g(self, opts, name):
                    path = f'/clickhouse/{name}'
                    settings.OVERRIDE.get(path, path)
                    key = '{}/{}'.format(opts['path'], opts['db'])
                    _pool_cache.get(key)
                    state = self.backend.name + '_state'
                    self.request.session.get(state)
                    request.session.get('/looks/like/a/path')
                    self.session.get(self.base_url + 'items')
                """
            }
        )
        expected = {('GET', '/real/path'), ('GET', '/two/args'), ('GET', '/looks/like/a/path'), ('GET', '/items')}
        self.assertEqual(requests_(ex), expected)

    def test_test_code_is_flagged(self):
        ex = extract(
            {
                'svc/mod.py': """
                def test_thing():
                    requests.get('/in-test-function')

                class TestThing:
                    def check(self):
                        requests.get('/in-test-class')

                def prod():
                    requests.get('/prod')
                """,
                'tests/test_api.py': """
                requests.get('/in-test-file')
                """,
                '.github/workflows/scripts/bootstrap.py': """
                requests.get('http://snuba:1218/health')
                """,
                'bin/tool.py': """
                requests.get('/from-bin')
                """,
                'pkg/bin/run.py': """
                requests.get('/nested-bin')
                """,
            }
        )
        self.assertEqual(requests_(ex), {('GET', '/prod'), ('GET', '/nested-bin')})
        self.assertEqual(
            requests_(ex, test=True),
            {
                ('GET', '/in-test-function'),
                ('GET', '/in-test-class'),
                ('GET', '/in-test-file'),
                ('GET', '/health'),
                ('GET', '/from-bin'),
            },
        )


class ForwardingTest(unittest.TestCase):
    def test_wrapper_chain_resolves_at_the_caller(self):
        ex = extract(
            {
                'src/app/lang/symbolicator.py': """
                from urllib.parse import urljoin

                class Symbolicator:
                    def _process(self, task_name, path, **kwargs):
                        session = SymbolicatorSession(url=self.base_url)
                        if task_id:
                            return session.query_task(task_id)
                        return session.create_task(path, **kwargs)

                    def process_payload(self):
                        return self._process('symbolicate_stacktraces', 'symbolicate', json={})

                    def process_js(self):
                        return self._process('js', path='symbolicate-js')

                class SymbolicatorSession:
                    def _request(self, method, path, **kwargs):
                        url = urljoin(self.url, path)
                        return self.session.request(method, url, **kwargs)

                    def create_task(self, path, **kwargs):
                        return self._request(method='post', path=path, **kwargs)

                    def query_task(self, task_id):
                        task_url = f'requests/{task_id}'
                        return self._request('get', task_url)

                    def recurse(self, path):
                        return self.recurse(path)
                """
            }
        )
        self.assertEqual(
            requests_(ex), {('POST', '/symbolicate'), ('POST', '/symbolicate-js'), ('GET', '/requests/{task_id}')}
        )
        c = call(ex, '/symbolicate')
        self.assertEqual((c.line, c.function), (12, 'Symbolicator.process_payload'))
        self.assertTrue(
            {'SymbolicatorSession', 'self.session', 'create_task', 'src/app/lang/symbolicator.py'} <= c.hints
        )
        poll = call(ex, '/requests/{task_id}')
        self.assertEqual((poll.line, poll.function), (27, 'SymbolicatorSession.query_task'))

    def test_template_wrapper_and_callers_in_other_files(self):
        ex = extract(
            {
                'src/app/rpc.py': """
                def make_rpc_request(endpoint_name, class_version='v1', referrer=None):
                    return pool.urlopen('POST', f'/rpc/{endpoint_name}/{class_version}')

                def get_trace(req):
                    return make_rpc_request('EndpointGetTrace', 'v1')

                def generic(req):
                    name = req.__class__.__name__
                    return make_rpc_request(name)

                def table(req):
                    return make_rpc_request(*args)
                """,
                'src/app/other.py': """
                from app.rpc import make_rpc_request

                def stats(req):
                    make_rpc_request(endpoint_name='EndpointStats')
                """,
                'src/app/base.py': """
                class Api:
                    def send(self, base):
                        return requests.get(base + '/health')

                    @staticmethod
                    def fetch(method, url):
                        return requests.request(method, url)

                def caller(api):
                    api.send(settings.SNUBA_URL)
                    Api.fetch('DELETE', '/fetched')
                """,
            }
        )
        self.assertEqual(
            requests_(ex),
            {
                ('POST', '/rpc/{endpoint_name}/{class_version}'),
                ('POST', '/rpc/endpointgettrace/v1'),
                ('POST', '/rpc/endpointstats/v1'),
                ('POST', '/rpc/{__name__}/v1'),
                ('GET', '/health'),
                ('DELETE', '/fetched'),
            },
        )
        stats = call(ex, '/rpc/endpointstats/v1')
        self.assertEqual((stats.file, stats.function), ('src/app/other.py', 'stats'))
        health = [c for c in ex.calls if str(c.path) == '/health']
        self.assertEqual({c.line for c in health}, {4, 11})
        self.assertIn('settings.SNUBA_URL', next(c for c in health if c.line == 11).hints)

    def test_method_decided_by_the_callers_arguments(self):
        ex = extract(
            {
                'src/app/http.py': """
                def safe_urlopen(url, method=None, data=None, json=None, verify=True):
                    if method is None:
                        method = 'POST' if (data or json) else 'GET'
                    return session.request(method=method, url=url)

                def flagged(url, upload=False, mode=''):
                    verb = 'PUT' if upload and not mode else 'GET'
                    return session.request(verb, url)

                def sized(url, size=0, extra=None):
                    return session.request('POST' if size is not None and size else 'GET', url)
                """,
                'src/app/beacon.py': """
                from app.http import safe_urlopen, flagged, sized

                def send(payload, verb):
                    safe_urlopen('https://x.io/beacon', json=payload)
                    safe_urlopen('https://x.io/fetch', data=None)
                    safe_urlopen('https://x.io/put', method='put', data={'a': 1})
                    safe_urlopen('https://x.io/empty', data='', json=[])
                    safe_urlopen('https://x.io/dynamic', method=verb)
                    flagged('https://x.io/upload', upload=True)
                    flagged('https://x.io/mode', upload=True, mode='x')
                    flagged('https://x.io/unknown', upload=maybe(), mode=other)
                    sized('https://x.io/sized', size=3)
                    sized('https://x.io/none', size=None)
                    sized('https://x.io/zero', 0)
                """,
            }
        )
        self.assertEqual(
            requests_(ex),
            {
                ('POST', '/beacon'),
                ('GET', '/fetch'),
                ('PUT', '/put'),
                ('GET', '/empty'),
                (ANY, '/dynamic'),
                ('PUT', '/upload'),
                ('GET', '/mode'),
                ('GET', '/unknown'),
                ('POST', '/sized'),
                ('GET', '/none'),
                ('GET', '/zero'),
            },
        )

    def test_fan_out_is_forwarded_once_per_function(self):
        lines = ['import requests', 'def f0(p, q):', "    return requests.get('/a/' + p + '/' + q)"]
        for k in range(1, 4):
            lines += [f'def f{k}(p, q):'] + [f'    f{k - 1}(p, q)'] * 30
        lines += ['def main():', "    f3('x', 'y')"]
        settle = python._Extractor._settle
        counter = mock.Mock(side_effect=lambda *a: settle(*a))
        with mock.patch.object(python._Extractor, '_settle', lambda *a: counter(*a)):
            ex = extract({'src/fan.py': '\n'.join(lines) + '\n'})
        self.assertEqual(requests_(ex), {('GET', '/a/{p}/{q}'), ('GET', '/a/x/y')})
        self.assertLess(counter.call_count, 200)  # 30 call sites per level, not 30 ** 3 chains

    def test_settles_per_request_are_capped(self):
        with mock.patch.object(python, 'MAX_SETTLES', 2):
            ex = extract(
                {
                    'src/w.py': """
                    def w(path):
                        return requests.get(path)

                    def a():
                        w('/one')
                        w('/two')
                    """
                }
            )
        self.assertEqual(len(requests_(ex)), 1)  # settled at the wrapper and at one caller only

    def test_self_attributes_are_read_once_per_class(self):
        methods = ''.join(f"    def m{i}(self):\n        return self.client.get('/r{i}')\n" for i in range(50))
        src = 'class C:\n    def __init__(self):\n        self.client = make_client()\n' + methods
        walk, roots = python.walk, []

        def counting(node, types=None):
            roots.append(node.parent.type)
            return walk(node, types)

        with mock.patch.object(python, 'walk', counting):
            ex = extract({'src/c.py': src})
        self.assertEqual(len(requests_(ex)), 50)
        self.assertIn('make_client()', call(ex, '/r7').hints)
        self.assertEqual(roots.count('class_definition'), 1)


class PayloadTest(unittest.TestCase):
    def test_reverse_names_and_hints(self):
        ex = extract(
            {
                'src/app/native/sources.py': """
                '''Symbol sources.'''
                from django.urls import reverse

                def get_internal_source(project):
                    '''Internal callers (e.g. Relay) get another URL.'''
                    url = '{}{}'.format(prefix(), reverse('dsym-files', kwargs={'org': project.org}))
                    return {'type': 'internal', 'url': url, 'service': 'symbolicator-source'}

                def get_sources(project):
                    relay_state = request.POST.get('RelayState')
                    return [get_internal_source(project)]

                def lookup_url(project):
                    return reverse('artifact-lookup')

                def lookup_source(project):
                    return {'url': lookup_url(project)}

                reverse(name_var)
                urls.reverse(viewname='module-level')
                items.reverse()
                reverse(f'{prefix}-x')
                """,
                'src/app/native/symbolicator.py': """
                from app.native.sources import lookup_source

                class Symbolicator:
                    def process_js(self):
                        return lookup_source(self.project)
                """,
                'tests/test_views.py': """
                from app.native.sources import lookup_source

                def test_view(client):
                    client.get(reverse('dsym-files'))

                def test_lookup():
                    lookup_source(None)
                """,
            }
        )
        payloads = {(c.route_name, c.test) for c in ex.calls if c.kind == 'payload'}
        self.assertEqual(
            payloads, {('dsym-files', False), ('artifact-lookup', False), ('module-level', False), ('dsym-files', True)}
        )
        dsym = next(c for c in ex.calls if c.route_name == 'dsym-files' and not c.test)
        self.assertIsNone(dsym.path)
        self.assertIn('symbolicator-source', dsym.hints)
        self.assertIn('get_sources', dsym.hints)
        self.assertIn("'''Symbol sources.'''", dsym.hints)
        self.assertFalse({'relay_state', 'RelayState'} & dsym.hints)  # a caller's own words name services by chance
        self.assertFalse(any('Relay)' in h for h in dsym.hints))  # the function's docstring is prose about others
        lookup = next(c for c in ex.calls if c.route_name == 'artifact-lookup')
        self.assertIn('src/app/native/symbolicator.py', lookup.hints)
        self.assertIn('Symbolicator.process_js', lookup.hints)
        self.assertNotIn('tests/test_views.py', lookup.hints)
        self.assertNotIn('test_lookup', lookup.hints)


if __name__ == '__main__':
    unittest.main()
