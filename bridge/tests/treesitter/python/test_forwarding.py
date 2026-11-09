import unittest
from unittest import mock

from atlas_bridge.adapters.treesitter.kit import Syntax
from atlas_bridge.adapters.treesitter.python.calls import RequestRun, Settler
from atlas_bridge.core.http import ANY

from .support import call, extract, requests_


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

    def test_branches_on_a_parameter_are_decided_per_caller(self):
        ex = extract(
            {
                'ml/api.py': """
                class MLApi(BaseHTTPAPI):
                    def _request(self, suffix, request=None, method='POST', *args, **kwargs):
                        url = f'{self._url}/{suffix}'
                        if method == 'POST':
                            return self.post(url=url, json=request, *args, **kwargs)
                        elif method == 'PUT':
                            return self.put(url, json=request)
                        else:
                            return self.get(url=url, *args, **kwargs)

                    def health(self):
                        return self._request('health', method='GET', timeout=1)

                    def predict(self, tasks):
                        return self._request('predict', {'tasks': tasks})

                    def replace(self, key):
                        return self._request(f'models/{key}', method='PUT')

                    def either(self, verb):
                        return self._request('either', method=verb)

                    def lookup(self, mapping):
                        return mapping.get('key', 'default')
                """,
            }
        )
        found = requests_(ex)
        self.assertEqual(
            {r for r in found if r[1] != '/either'},
            {('GET', '/health'), ('POST', '/predict'), ('PUT', '/models/{key}')},
        )
        self.assertEqual({m for m, p in found if p == '/either'}, {'GET', 'POST', 'PUT'})  # not decided here

    def test_fan_out_is_forwarded_once_per_function(self):
        lines = ['import requests', 'def f0(p, q):', "    return requests.get('/a/' + p + '/' + q)"]
        for k in range(1, 4):
            lines += [f'def f{k}(p, q):'] + [f'    f{k - 1}(p, q)'] * 30
        lines += ['def main():', "    f3('x', 'y')"]
        settle = Settler.settle
        counter = mock.Mock(side_effect=lambda *a: settle(*a))
        with mock.patch.object(Settler, 'settle', lambda *a: counter(*a)):
            ex = extract({'src/fan.py': '\n'.join(lines) + '\n'})
        self.assertEqual(requests_(ex), {('GET', '/a/{p}/{q}'), ('GET', '/a/x/y')})
        self.assertLess(counter.call_count, 200)  # 30 call sites per level, not 30 ** 3 chains

    def test_settles_per_request_are_capped(self):
        with mock.patch.object(RequestRun, 'MAX_SETTLES', 2):
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
        walk, roots = Syntax.walk, []

        def counting(node, types=None):
            roots.append(node.parent.type)
            return walk(node, types)

        with mock.patch.object(Syntax, 'walk', staticmethod(counting)):
            ex = extract({'src/c.py': src})
        self.assertEqual(len(requests_(ex)), 50)
        self.assertIn('make_client()', call(ex, '/r7').hints)
        self.assertEqual(roots.count('class_definition'), 1)
