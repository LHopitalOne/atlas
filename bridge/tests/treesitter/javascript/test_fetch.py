import time
import unittest

from .support import Repository

calls = Repository.calls


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


if __name__ == '__main__':
    unittest.main()
