import unittest

from .support import Repository

calls = Repository.calls


def run(files):
    return Repository(files).extract()


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

    def test_aliases_and_imported_client_variables(self):
        found = {
            (c.method, str(c.path))
            for c in run(
                {
                    'src/api.ts': "export class Client { baseUrl = '/api/0'; }\n",
                    'src/shared.ts': 'export const SHARED = new Client();\n',
                    'src/views.ts': "import {SHARED} from 'app/shared';\n"
                    'const made = new Client();\n'
                    'const alias = made;\n'  # followed through the binding to `new Client()`
                    'const viaImport = SHARED;\n'  # followed to the imported module variable
                    "export function f() { alias.get('/a/'); viaImport.get('/b/'); }\n",
                }
            ).calls
        }
        self.assertEqual(found, {('GET', '/api/0/a'), ('GET', '/api/0/b')})

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


if __name__ == '__main__':
    unittest.main()
