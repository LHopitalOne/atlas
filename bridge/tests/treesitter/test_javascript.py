import os
import tempfile
import time
import unittest

from atlas_bridge.adapters.treesitter import common, javascript
from atlas_bridge.core.http import ANY


def run(files, repo='web'):
    """Write {path: source} to a temporary repository and extract from every file."""
    with tempfile.TemporaryDirectory() as root:
        for path, source in files.items():
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w') as f:
                f.write(source)
        return javascript.extract(repo, root, sorted(files))


def calls(source, path='src/a.js'):
    return {(c.method, str(c.path)): c for c in run({path: source}).calls}


def routes(files):
    return {(m, str(r.path)): r for r in run(files).routes for m in r.methods}


class FetchTest(unittest.TestCase):
    def test_base_constant_and_template(self):
        found = calls(
            "const BASE = process.env.API_URL || 'http://api:8000';\n"
            'export async function placeOrder(items) {\n'
            "  return fetch(`${BASE}/orders`, { method: 'POST', body: JSON.stringify({ items }) });\n"
            '}\n'
            'export const loadOrder = async (id) => (await fetch(`${BASE}/orders/${id}`)).json();\n'
        )
        self.assertEqual(sorted(found), [('GET', '/orders/{id}'), ('POST', '/orders')])
        post = found[('POST', '/orders')]
        self.assertEqual((post.repo, post.file, post.line, post.function), ('web', 'src/a.js', 3, 'placeOrder'))
        self.assertTrue({'BASE', 'api', "process.env.API_URL || 'http://api:8000'", 'src/a.js'} <= post.hints)
        self.assertEqual(found[('GET', '/orders/{id}')].function, 'loadOrder')
        self.assertFalse(post.test)

    def test_unresolved_base_becomes_hint(self):
        found = calls('function f(id) { return fetch(`${API_URL}/users/${id}?x=1`); }')
        self.assertIn('API_URL', found[('GET', '/users/{id}')].hints)

    def test_concatenation_ternary_and_local_binding(self):
        found = calls(
            "const ROOT = '/v1';\n"
            'function f(id, flag) {\n'
            "  const url = ROOT + '/items/' + id;\n"
            '  fetch(url, {method: m});\n'
            "  fetch(flag ? '/a/b' : '/c');\n"
            "  fetch(new URL('/x/y', base));\n"
            "  window.fetch('/w', opts);\n"
            '  fetch(2);\n'
            '}\n'
            "const opts = {method: 'put'};\n"
        )
        self.assertEqual(sorted(found), [('ANY', '/v1/items/{id}'), ('GET', '/a/b'), ('GET', '/x/y'), ('PUT', '/w')])
        self.assertTrue({'url', 'ROOT'} <= found[('ANY', '/v1/items/{id}')].hints)
        self.assertIn('base', found[('GET', '/x/y')].hints)

    def test_dynamic_urls_are_skipped(self):
        source = 'function f(u, o) { fetch(u); fetch(o.url); fetch(); fetch(`${u}`); fetch(a && b); }'
        self.assertEqual(calls(source), {})

    def test_path_variable_glued_to_a_literal_is_a_tail(self):
        found = calls(
            'function f(props, host) {\n'
            "  fetch(new URL(prefix + '/api/0' + apiUrl, host));\n"
            '  fetch(`/api/1${getAttachmentUrl(props)}?download`);\n'
            '  fetch(`/v${version}/x`);\n'
            '}\n'
        )
        self.assertEqual(
            sorted(found), [('GET', '/api/0/{*apiUrl}'), ('GET', '/api/1/{*props}'), ('GET', '/v{version}/x')]
        )

    def test_parameters_shadow_outer_bindings(self):
        found = calls(
            "const url = '/module';\n"
            'function f(url) { return fetch(url); }\n'
            'function g({url}) { return fetch(url); }\n'
            'const h = url => fetch(url);\n'
            'for (const url of list) fetch(url);\n'
            'try {} catch (url) { fetch(url); }\n'
            'function d(o) { const {url} = o; return fetch(url); }\n'
            "function k(x = url) { return fetch(url + '/k'); }\n"
        )
        self.assertEqual(sorted(found), [('GET', '/module/k')])

    def test_bindings_are_resolved_once(self):
        source = "const v0 = '/p';\n" + ''.join(
            f'const v{i} = ' + ' + '.join([f'v{i - 1}'] * 20) + ';\n' for i in range(1, 6)
        )
        start = time.perf_counter()
        found = calls(source + 'fetch(v5);\n')
        self.assertLess(time.perf_counter() - start, 2)
        self.assertEqual(found, {})  # longer than any URL

    def test_url_builder_call(self):
        found = calls(
            'async function remove(api, org) {\n'
            "  return api.requestPromise(getApiUrl('/projects/$org/:project/', {path: {org}}), {method: 'DELETE'});\n"
            '}\n'
        )
        self.assertIn(('DELETE', '/projects/{org}/{project}'), found)
        self.assertIn('getApiUrl', found[('DELETE', '/projects/{org}/{project}')].hints)

    def test_typescript_wrappers(self):
        source = 'class Store { async load(id: string) { return fetch<Item>((`/items/${id}`) as string, init!); } }'
        found = calls(source, 'src/store.ts')
        self.assertEqual(found[('GET', '/items/{id}')].function, 'load')
        self.assertIn('Store', found[('GET', '/items/{id}')].hints)
        found = calls('const x = () => <div>{fetch((u as string) + "/z")}</div>;', 'src/view.tsx')
        self.assertEqual(sorted(found), [('GET', '/{u}/z')])
        self.assertIn(('GET', '/{u}/z'), calls("fetch(<string>u + '/z');", 'src/a.ts'))


class AxiosAndClientTest(unittest.TestCase):
    def test_axios_forms(self):
        found = calls(
            "import axios from 'axios';\n"
            "axios.get('/a');\n"
            "axios.delete('/b');\n"
            "axios({url: '/c', method: 'patch'});\n"
            "axios('/d', {method: 'POST'});\n"
            "axios.request({url: '/e'});\n"
            "axios.request('/f', {method: 'HEAD'});\n"
            'axios.request({data: 1});\n'
            'axios();\n'
        )
        self.assertEqual(
            sorted(found),
            [('DELETE', '/b'), ('GET', '/a'), ('GET', '/e'), ('HEAD', '/f'), ('PATCH', '/c'), ('POST', '/d')],
        )

    def test_client_receivers(self):
        found = calls(
            "import http from './http';\n"
            "const api = axios.create({baseURL: 'http://orders:9000'});\n"
            'export class Service {\n'
            '  client = new Client(SETTINGS.ORDERS);\n'
            '  constructor() { this.session = makeSession(); }\n'
            "  list() { return this.client.get('items'); }\n"
            '  save(id) { return api.put(`/items/${id}`, body); }\n'
            "  ping = () => http.post('health');\n"
            "  more() { return this.session.del('/s'); }\n"
            '}\n'
            "superagent.patch('/sa');\n"
            "request(app).get('/sup');\n"
        )
        self.assertEqual(
            sorted(found),
            [('DELETE', '/s'), ('GET', '/items'), ('GET', '/sup'), ('PATCH', '/sa'), ('POST', '/health'),
             ('PUT', '/items/{id}')],
        )  # fmt: skip
        self.assertIn('new Client(SETTINGS.ORDERS)', found[('GET', '/items')].hints)
        self.assertIn("axios.create({baseURL: 'http://orders:9000'})", found[('PUT', '/items/{id}')].hints)
        self.assertIn('./http', found[('POST', '/health')].hints)
        self.assertEqual(found[('POST', '/health')].function, 'ping')
        self.assertIn('makeSession()', found[('DELETE', '/s')].hints)

    def test_other_receivers_need_a_path(self):
        found = calls(
            'function f(params, map) {\n'
            "  params.get('page');\n"
            "  headers.get('content-type');\n"
            "  requestHeaders.get('Accept');\n"
            '  map.get(key);\n'
            "  store.get('/looks/like/a/path');\n"
            "  cache.post('http://cache:1/x');\n"
            "  routeMap.get('/settings/');\n"
            "  thing.get('/looks/like/a/path');\n"
            '  thing.get(`${a}/children`);\n'
            '  thing.get(`${API_ROOT}/v/${a}`);\n'
            "  api.all('/x');\n"
            '  api.get();\n'
            "  api.fetch('/f');\n"
            "  handler.fetch('/no');\n"
            "  other.request('/r2');\n"
            "  other.request('no');\n"
            "  other.request({url: '/no'});\n"
            "  searchParams.request('/no');\n"
            "  api.request('/r', {method: 'post'});\n"
            "  api.route('/no');\n"
            '}\n'
        )
        self.assertEqual(
            sorted(found),
            [('GET', '/f'), ('GET', '/looks/like/a/path'), ('GET', '/r2'), ('GET', '/v/{a}'), ('POST', '/r')],
        )

    def test_map_and_cache_keys_are_not_requests(self):
        found = calls(
            'async function f(resp) {\n'
            "  const cache = await caches.open('v1');\n"
            "  cache.put('/api/client-config/', resp);\n"
            '  const m = new Map();\n'
            "  m.get('/x');\n"
            "  const box = caches.open('v2');\n"
            "  box.put('/y', resp);\n"
            '}\n'
        )
        self.assertEqual(found, {})

    def test_client_names_with_other_words(self):
        found = calls(
            "QUERY_API_CLIENT.requestPromise('/organizations/acme/code-mappings/', {method: 'GET'});\n"
            "platformClient.get('platforms/list');\n"
            "datasetClient.get('datasets');\n"
        )
        self.assertEqual(
            sorted(found),
            [('GET', '/datasets'), ('GET', '/organizations/acme/code-mappings'), ('GET', '/platforms/list')],
        )

    def test_key_value_clients_and_numbers(self):
        found = calls(
            'const client = redis.createClient();\n'
            "function f(id) { client.get('user:' + id); client.del('session'); return client.get('views'); }\n"
            "client.get('/really/a/path');\n"
            'api.get(5);\n'
            "api.get('user:1');\n"
        )
        self.assertEqual(sorted(found), [('GET', '/really/a/path')])

    def test_function_names(self):
        found = calls(
            "const handlers = { load: () => api.get('/1'), save() { return api.post('/2'); } };\n"
            "module.exports.run = function () { return api.put('/3'); };\n"
            "useEffect(() => { api.delete('/4'); });\n"
            "const named = function inner() { return api.patch('/5'); };\n"
        )
        self.assertEqual(
            {k: c.function for k, c in found.items()},
            {('GET', '/1'): 'load', ('POST', '/2'): 'save', ('PUT', '/3'): 'run', ('DELETE', '/4'): '',
             ('PATCH', '/5'): 'inner'},
        )  # fmt: skip


class ClientBaseTest(unittest.TestCase):
    CLIENT = (
        'export class Client {\n'
        '  baseUrl: string;\n'
        "  constructor(options = {}) { this.baseUrl = options.baseUrl ?? '/api/0'; }\n"
        '  requestPromise(path, options) { return fetch(this.baseUrl + path, options); }\n'
        '}\n'
    )

    def test_repository_client_class_default(self):
        found = {
            (c.file, c.method, str(c.path))
            for c in run(
                {
                    'src/api.tsx': self.CLIENT,
                    'src/__mocks__/api.tsx': "class Client { baseUrl = ''; }\n",
                    'src/useApi.tsx': "import {Client} from 'app/api';\n"
                    'export function useApi() { const api = useRef(new Client()); return api.current; }\n',
                    'src/apiFetch.tsx': "import {Client} from 'app/api';\n"
                    'export const QUERY_API_CLIENT = new Client();\n',
                    'src/views.tsx': "import {QUERY_API_CLIENT} from 'app/apiFetch';\n"
                    'export function remove(api: Client, org: string) {\n'
                    "  return api.requestPromise(`/projects/${org}/`, {method: 'DELETE'});\n"
                    '}\n'
                    'export function View() {\n'
                    '  const api = useApi();\n'
                    "  api.requestPromise('/teams/');\n"
                    "  QUERY_API_CLIENT.requestPromise('/organizations/acme/');\n"
                    "  new Client({baseUrl: ''}).requestPromise('/extensions/x/');\n"
                    "  api.requestPromise('/api/0/already/');\n"
                    "  api.requestPromise('https://example.com/abs');\n"
                    "  props.api.requestPromise('/unknown/');\n"
                    '}\n'
                    'class Old { api = new Client(); load() { return this.api.requestPromise(`/old/`); } }\n',
                }
            ).calls
        }
        self.assertTrue(
            {
                ('src/views.tsx', 'DELETE', '/api/0/projects/{org}'),
                ('src/views.tsx', 'GET', '/api/0/teams'),
                ('src/views.tsx', 'GET', '/api/0/organizations/acme'),
                ('src/views.tsx', 'GET', '/extensions/x'),
                ('src/views.tsx', 'GET', '/api/0/already'),
                ('src/views.tsx', 'GET', '/abs'),
                ('src/views.tsx', 'GET', '/unknown'),
                ('src/views.tsx', 'GET', '/api/0/old'),
            }
            <= found,
            found,
        )

    def test_typed_members_and_object_stores(self):
        found = {
            (c.line, str(c.path))
            for c in run(
                {
                    'src/api.tsx': self.CLIENT,
                    'src/views.tsx': 'type Props = {api: Client; org: string};\n'
                    "function tags({api, org}: Props & {api: Client}) { return api.requestPromise('/tags/'); }\n"
                    "function teams({api}: Props) { return api.requestPromise('/teams/'); }\n"
                    "class View { load() { return this.props.api.requestPromise('/view/'); } }\n"
                    "const Store = { api: new Client(), init() { this.api.requestPromise('/store/'); } };\n"
                    "const Other = { init() { this.client = new Client(); }, load() { this.client.get('/o/'); } };\n"
                    "function plain(api) { return api.requestPromise('/plain/'); }\n"
                    "function body(props) { const {api} = props; return api.requestPromise('/body/'); }\n",
                }
            ).calls
        }
        self.assertEqual(
            found,
            {(2, '/api/0/tags'), (3, '/api/0/teams'), (4, '/api/0/view'), (5, '/api/0/store'), (6, '/api/0/o'),
             (7, '/api/0/plain'), (8, '/api/0/body')},
        )  # fmt: skip

    def test_client_class_without_a_default(self):
        found = calls(
            'class Remote { constructor(opts) { this.baseURL = opts.baseURL; } }\n'
            'class Plain { baseUrl = ""; }\n'
            'const remote = new Remote(settings);\n'
            'const plain = new Plain();\n'
            "remote.get('/items/');\n"
            "plain.get('/other/');\n"
        )
        self.assertEqual(sorted(found), [('GET', '/other'), ('GET', '/{base}/items')])

    def test_base_url_option(self):
        found = calls(
            "const api = axios.create({baseURL: 'http://orders:8000/api/v1'});\n"
            'const kyApi = ky.create({prefixUrl: `${API_ROOT}/v2`});\n'
            'export const loadOrder = (id) => api.get(`/orders/${id}`);\n'
            "export const loadUser = (id) => kyApi.get('users/' + id);\n"
        )
        self.assertEqual(sorted(found), [('GET', '/api/v1/orders/{id}'), ('GET', '/v2/users/{id}')])
        self.assertIn('orders', found[('GET', '/api/v1/orders/{id}')].hints)
        self.assertIn('API_ROOT', found[('GET', '/v2/users/{id}')].hints)


class TestFlagTest(unittest.TestCase):
    def test_test_code(self):
        source = "describe('x', () => { it('y', async () => { await fetch('/a/b'); }); });\nfetch('/c');\n"
        found = calls(source)
        self.assertTrue(found[('GET', '/a/b')].test)
        self.assertFalse(found[('GET', '/c')].test)
        self.assertTrue(calls("fetch('/c');", 'src/a.spec.ts')[('GET', '/c')].test)
        self.assertTrue(calls("fetch('/c');", '__tests__/a.js')[('GET', '/c')].test)
        found = calls("describe.each([1])('x', () => fetch('/e'));\n!function (w) { fetch('/iife'); }(window);\n")
        self.assertTrue(found[('GET', '/e')].test)
        self.assertFalse(found[('GET', '/iife')].test)

    def test_long_receivers_are_cheap(self):
        source = '(function(){' + 'var aN=g(h(k(N)));' * 20000 + '})().client.get("/y");' + 'api.get("/z");' * 2000
        start = time.perf_counter()
        found = calls(source)
        self.assertLess(time.perf_counter() - start, 3)
        self.assertEqual(sorted(found), [('GET', '/y'), ('GET', '/z')])


class RouteTest(unittest.TestCase):
    def test_express_routes(self):
        found = routes(
            {
                'server.js': "const express = require('express');\n"
                'const app = express();\n'
                'const r = express.Router();\n'
                "app.get('/orders/:id', auth, getOrder);\n"
                "app.post('/orders', (req, res) => {});\n"
                "app.all('/files/*', files.serve);\n"
                "r.delete('/x/:a(\\\\d+)/:b?', del);\n"
                "app.get('/hono/:id{[0-9]+}', h);\n"
                "router.get('named', '/koa/:slug', koaHandler);\n"
                "app.route('/book').get(getBook).put(putBook);\n"
                "app.get('/splat/*rest', h);\n"
                "app.get('/no-handler');\n"
                "app.get('setting');\n"
                "thing.get('/not/a/route', h);\n"
            }
        )
        self.assertEqual(
            {k: r.handler for k, r in found.items()},
            {
                ('GET', '/orders/{id}'): 'getOrder',
                ('POST', '/orders'): '',
                (ANY, '/files/{*rest}'): 'files.serve',
                ('DELETE', '/x/{a}/{b}'): 'del',
                ('GET', '/hono/{id}'): 'h',
                ('GET', '/koa/{slug}'): 'koaHandler',
                ('GET', '/book'): 'getBook',
                ('PUT', '/book'): 'putBook',
                ('GET', '/splat/{*rest}'): 'h',
            },
        )
        r = found[('GET', '/orders/{id}')]
        self.assertEqual((r.repo, r.file, r.line, r.framework), ('web', 'server.js', 4, 'express'))

    def test_fastify_route(self):
        found = routes(
            {
                'f.ts': "fastify.route({method: ['GET', 'POST'], url: '/f/:id', handler: fh});\n"
                "fastify.route({method: 'DELETE', path: '/g', handler(req) {}});\n"
                "fastify.route({url: '/h'});\n"
                'fastify.route({url: dynamic});\n'
            }
        )
        self.assertEqual(sorted(found), [(ANY, '/h'), ('DELETE', '/g'), ('GET', '/f/{id}'), ('POST', '/f/{id}')])
        self.assertEqual(found[('GET', '/f/{id}')].handler, 'fh')

    def test_mount_in_same_file(self):
        found = routes(
            {
                'app.js': 'const app = express();\n'
                'const orders = express.Router();\n'
                "orders.get('/:id', show);\n"
                "app.use('/api', orders);\n"
                'app.use(orders);\n'
                "app.use('/x', unknownThing);\n"
            }
        )
        self.assertEqual(sorted(found), [('GET', '/api/{id}')])

    def test_mount_cycles(self):
        found = routes(
            {
                'app.js': 'const router = express.Router();\n'
                "router.use('/x', router);\n"
                "router.get('/y', h);\n"
                'const a = express.Router();\n'
                'const b = express.Router();\n'
                "a.use('/b', b);\n"
                "b.use('/a', a);\n"
                "b.get('/z', h);\n"
            }
        )
        self.assertEqual(sorted(found), [('GET', '/b/z'), ('GET', '/y')])  # a cycle adds no prefix

    def test_mount_across_files(self):
        found = routes(
            {
                'src/app.js': "import orders from './routes/orders';\n"
                "import { users as people } from './routes/users';\n"
                "const misc = require('./routes/misc');\n"
                "import ext from 'external';\n"
                'const app = express();\n'
                'const api = express.Router();\n'
                "app.use('/api/v1', api);\n"
                "api.use('/orders', orders);\n"
                "api.use('/users', people);\n"
                "app.use('/misc', misc);\n"
                "app.use('/inline', require('./routes/inline.js'));\n"
                "app.use('/ext', ext);\n"
                "app.use('/missing', require('./routes/nope'));\n",
                'src/routes/orders.js': "const router = express.Router();\nrouter.get('/:id', show);\n"
                'export default router;\n',
                'src/routes/users.ts': "export const users = Router();\nusers.post('/', create);\n",
                'src/routes/misc/index.js': "const r = express.Router();\nr.get('/m', m);\nmodule.exports = r;\n",
                'src/routes/inline.js': "app.get('/i', i);\n",
            }
        )
        self.assertEqual(
            sorted(found),
            [('GET', '/api/v1/orders/{id}'), ('GET', '/inline/i'), ('GET', '/misc/m'), ('POST', '/api/v1/users')],
        )


class HelpersTest(unittest.TestCase):
    def test_express_path(self):
        self.assertEqual(javascript.express_path('users/:id'), '/users/{id}')
        self.assertEqual(javascript.express_path('/(.*)'), '/{*rest}')
        self.assertEqual(javascript.express_path('/a/files*'), '/a/{*rest}')
        self.assertEqual(javascript.express_path('/:from-:to'), '/{from}-{to}')
        self.assertEqual(javascript.express_path('/post/:date{[0-9]{1,3}}'), '/post/{date}')

    def test_precheck_and_size(self):
        big = 'x' * (common.MAX_BYTES + 1)
        self.assertEqual(run({'a.js': 'const x = 1;\n', 'b.js': big}).calls, [])

    def test_extension_grammar(self):
        for ext in ('.mjs', '.cjs', '.jsx', '.ts', '.tsx'):
            self.assertIn(('GET', '/a'), calls("fetch('/a');", 'src/a' + ext))


if __name__ == '__main__':
    unittest.main()
