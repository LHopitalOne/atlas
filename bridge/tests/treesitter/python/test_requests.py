import unittest

from atlas_bridge.core.http import ANY

from .support import call, extract, requests_


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

    def test_generated_client_request_with_a_named_method(self):
        ex = extract(
            {
                'sdk/tasks/raw_client.py': """
                class RawTasksClient:
                    def get(self, id):
                        client = self._client_wrapper.httpx_client
                        return client.request(f"api/tasks/{encode_path_param(id)}/", method="GET")

                    def delete(self, id):
                        return self._client_wrapper.httpx_client.request(path=f"api/tasks/{id}/", method="DELETE")

                    def legacy(self, session):
                        return session.request('PATCH', '/api/legacy/')
                """,
            }
        )
        self.assertEqual(
            requests_(ex), {('GET', '/api/tasks/{id}'), ('DELETE', '/api/tasks/{id}'), ('PATCH', '/api/legacy')}
        )

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

    def test_calls_come_in_file_line_and_path_order(self):
        ex = extract(
            {
                'b.py': "requests.get('/z')\nrequests.post('/y')\n",
                'a.py': """
                import requests
                def w(path):
                    return requests.get('/w/' + path)

                w('second')
                w('first')
                requests.get('/a')
                """,
            }
        )
        keys = [(c.file, c.line, str(c.path), c.method) for c in ex.calls]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(len(keys), 6)
