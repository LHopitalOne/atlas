import unittest

from .support import Repository

calls = Repository.calls


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


if __name__ == '__main__':
    unittest.main()
