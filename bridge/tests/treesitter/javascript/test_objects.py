import unittest

from atlas_bridge.adapters.treesitter.javascript.linker import ModuleLinker

from .support import Repository

CONFIG = (
    'export const config = {\n'
    '  orders: {\n'
    "    baseUrl: process.env.ORDERS_API_URL ?? 'http://localhost:8000',\n"
    "    endpoints: { list: '/orders', menu: '/menus' },\n"
    '  },\n'
    '} as const;\n'
)


def calls(files):
    return {(c.method, str(c.path)): c for c in Repository(files).extract().calls}


class ObjectValueTest(unittest.TestCase):
    def test_destructured_members_of_an_imported_config_object(self):
        found = calls(
            {
                'src/config.ts': CONFIG,
                'src/api.ts': "import { config } from './config';\n"
                'const { baseUrl, endpoints } = config.orders;\n'
                'export const menu = (id: number) => fetch(`${baseUrl}${endpoints.menu}/${id}`);\n'
                "export const place = () => fetch(`${baseUrl}${endpoints.list}`, { method: 'POST' });\n"
                'export const direct = () => fetch(config.orders.baseUrl + config.orders.endpoints.list);\n',
            }
        )
        self.assertEqual(sorted(found), [('GET', '/menus/{id}'), ('GET', '/orders'), ('POST', '/orders')])
        hints = found[('GET', '/menus/{id}')].hints
        self.assertTrue({'localhost', 'process.env.ORDERS_API_URL', 'endpoints.menu'} <= hints)

    def test_nested_patterns_freeze_and_commonjs_exports(self):
        found = calls(
            {
                'lib/urls.js': "const paths = Object.freeze({ users: '/users' });\n"
                "module.exports = { paths, api: { root: '/api/v2' } };\n",
                'lib/client.js': "const { paths, api: { root } } = require('./urls');\nfetch(root + paths.users);\n",
            }
        )
        self.assertEqual(sorted(found), [('GET', '/api/v2/users')])

    def test_export_clauses_and_default_exports(self):
        found = calls(
            {
                'src/routes/index.ts': "const ROUTES = { health: '/healthz' };\nexport { ROUTES as routes };\n",
                'src/defaults.ts': "export default { search: '/search/items' };\n",
                'src/use.ts': "import { routes } from './routes';\nimport defaults from './defaults';\n"
                'fetch(routes.health);\nfetch(defaults.search);\n',
            }
        )
        self.assertEqual(sorted(found), [('GET', '/healthz'), ('GET', '/search/items')])

    def test_what_cannot_be_followed_stays_unknown(self):
        found = calls(
            {
                'src/a.ts': "import { config } from 'some-package';\n"
                'function f(opts) {\n'
                '  fetch(`${config.base}/x/y`);\n'
                '  const { root } = opts;\n'
                '  fetch(`${root}/p/q`);\n'
                "  fetch(missing.member + '/m/n');\n"
                '}\n'
            }
        )
        self.assertEqual(sorted(found), [('GET', '/p/q'), ('GET', '/x/y'), ('GET', '/{member}/m/n')])

    def test_a_key_that_holds_a_url_is_not_a_request_path(self):
        found = calls({'src/a.ts': "const item = { key: 'cache:robots:https://example.com' };\ncache.get(item.key);\n"})
        self.assertEqual(found, {})

    def test_a_known_host_with_a_parameter_path_is_settled_at_the_callers(self):
        found = calls(
            {
                'src/config.ts': "export const HOST = 'https://api.example.com';\n",
                'src/api.ts': "import { HOST } from './config';\n"
                'export async function request(token, path) { return fetch(`${HOST}${path}`); }\n'
                "export const me = (t) => request(t, '/users/me');\n",
                'src/other.ts': "import { request } from 'undici';\nrequest(this.url, { method: 'GET' });\n",
            }
        )
        self.assertEqual(sorted(found), [('GET', '/users/me')])
        self.assertEqual(found[('GET', '/users/me')].file, 'src/api.ts')


class AliasImportTest(unittest.TestCase):
    """A base URL imported through a path alias (`$lib/...` in SvelteKit, `@/...` in Vite and Next) is followed to
    the one file the alias can name."""

    def test_sveltekit_lib_alias(self):
        found = calls(
            {
                'src/lib/constants.ts': "export const BASE = '';\nexport const API_BASE = `${BASE}/api/v1`;\n",
                'src/lib/apis/chats.ts': "import { API_BASE } from '$lib/constants';\n"
                "export const pinned = () => fetch(`${API_BASE}/chats/pinned`, { method: 'GET' });\n",
            }
        )
        self.assertEqual(sorted(found), [('GET', '/api/v1/chats/pinned')])

    def test_two_files_that_fit_leave_it_unknown_and_packages_are_not_aliases(self):
        ws = Repository.workspace(
            [('src/a/config.ts', 'export const A = 1;\n'), ('src/b/config.ts', 'export const B = 2;\n')]
        )
        linker = ws.linker()
        self.assertIsNone(linker.path('src/x.ts', '@/config'))
        self.assertEqual(linker.path('src/x.ts', '@/a/config'), 'src/a/config.ts')
        self.assertIsNone(linker.path('src/x.ts', '@scope/config'))


class LinkerTest(unittest.TestCase):
    def test_which_import_may_name_a_file(self):
        names = ModuleLinker.may_name
        self.assertTrue(names('src/a.ts', './lib/api', 'src/lib/api.ts'))
        self.assertTrue(names('src/a.ts', './lib', 'src/lib/index.ts'))
        self.assertTrue(names('src/a.ts', '@/lib/api', 'src/lib/api.ts'))
        self.assertTrue(names('src/a.ts', '~/lib', 'src/lib/index.js'))
        self.assertFalse(names('src/a.ts', 'undici', 'src/lib/api.ts'))
        self.assertFalse(names('src/a.ts', './other', 'src/lib/api.ts'))

    def test_files_are_read_once_and_up_to_a_limit(self):
        ws = Repository.workspace([('a.ts', 'export const A = 1;\n'), ('b.ts', 'export const B = 2;\n')])
        linker = ws.linker()
        self.assertIs(linker.module('x.ts', './a'), linker.module('x.ts', './a.js'))
        self.assertIsNone(linker.module('x.ts', 'react'))
        self.assertIsNone(linker.module('x.ts', './c'))
        linker.MAX_MODULES = 1
        self.assertIsNone(linker.module('x.ts', './b'))
        linker.release()


if __name__ == '__main__':
    unittest.main()
