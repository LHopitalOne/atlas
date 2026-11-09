import unittest

from atlas_bridge.adapters.treesitter.javascript.routes.nextpaths import NextPath
from atlas_bridge.core.http import ANY

from .support import Repository


def routes(files):
    return {(m, str(r.path)): r for r in Repository(files).extract().routes for m in r.methods}


class NextPathTest(unittest.TestCase):
    def test_pages_router_api_files(self):
        self.assertEqual(NextPath.pages_api('pages/api/notes/index.js'), '/api/notes')
        self.assertEqual(NextPath.pages_api('src/pages/api/notes/[id].ts'), '/api/notes/{id}')
        self.assertEqual(NextPath.pages_api('apps/web/pages/api/files/[...slug].tsx'), '/api/files/{*slug}')
        self.assertEqual(NextPath.pages_api('pages/api/docs/[[...slug]].js'), '/api/docs/{*slug}')
        self.assertEqual(NextPath.pages_api('pages/api.js'), '/api')
        for other in (
            'pages/index.js',
            'pages/notes/[id].js',
            'pages/api/x.test.js',
            'pages/api/types.d.ts',
            'api/x.js',
        ):
            self.assertIsNone(NextPath.pages_api(other), other)

    def test_app_router_route_files(self):
        self.assertEqual(NextPath.app_route('app/api/orders/route.ts'), '/api/orders')
        self.assertEqual(NextPath.app_route('src/app/(shop)/api/orders/[id]/route.js'), '/api/orders/{id}')
        self.assertEqual(NextPath.app_route('app/@modal/feed/[...all]/route.ts'), '/feed/{*all}')
        self.assertEqual(NextPath.app_route('app/route.ts'), '/')
        self.assertIsNone(NextPath.app_route('app/_lib/route.ts'))
        self.assertIsNone(NextPath.app_route('app/api/orders/page.tsx'))


class NextRoutesTest(unittest.TestCase):
    def test_pages_router_methods_from_req_method_checks(self):
        found = routes(
            {
                'pages/api/notes/index.js': 'export default async function handler(req, res) {\n'
                "  if (req.method === 'GET') return res.json([]);\n"
                "  if (req.method == 'POST') return res.status(201).end();\n"
                '}\n',
                'pages/api/notes/[id].ts': 'async function handler(req, res) {\n'
                '  switch (req.method) {\n'
                "    case 'GET': return res.json({});\n"
                "    case 'DELETE': return res.status(204).end();\n"
                '    default: return res.status(405).end();\n'
                '  }\n'
                '}\n'
                "export default withLog('/api/notes/{id}', handler);\n",
                'pages/api/search.js': 'export default function search(req, res) {\n'
                "  if (req.method !== 'GET') return res.status(405).end();\n"
                "  if (['GET', 'HEAD'].includes(req.method)) {}\n"
                '}\n',
                'pages/api/ping.js': 'const ping = (req, res) => res.end();\nmodule.exports = ping;\n',
            }
        )
        self.assertEqual(
            sorted(found),
            [
                (ANY, '/api/ping'),
                ('DELETE', '/api/notes/{id}'),
                ('GET', '/api/notes'),
                ('GET', '/api/notes/{id}'),
                ('GET', '/api/search'),
                ('HEAD', '/api/search'),
                ('POST', '/api/notes'),
            ],
        )
        post = found[('POST', '/api/notes')]
        self.assertEqual(
            (post.file, post.line, post.handler, post.framework), ('pages/api/notes/index.js', 3, 'handler', 'nextjs')
        )
        self.assertEqual(found[(ANY, '/api/ping')].handler, 'ping')

    def test_app_router_exported_methods(self):
        found = routes(
            {
                'app/api/orders/[id]/route.ts': 'export async function GET(request: Request) {}\n'
                'const update = async () => {};\n'
                'export { update as PUT };\n'
                'export const DELETE = update;\n'
                'export const dynamic = "force-dynamic";\n',
            }
        )
        self.assertEqual(
            sorted(found), [('DELETE', '/api/orders/{id}'), ('GET', '/api/orders/{id}'), ('PUT', '/api/orders/{id}')]
        )
        self.assertEqual(
            (found[('GET', '/api/orders/{id}')].line, found[('GET', '/api/orders/{id}')].handler), (1, 'GET')
        )

    def test_files_that_are_not_routes(self):
        found = routes(
            {
                'pages/api/helpers.js': 'export function helper() {}\n',  # no default export: Next.js serves nothing
                'pages/api/notes.test.js': 'export default function handler() {}\n',
                'src/app/route.ts': 'export function helper() {}\n',
            }
        )
        self.assertEqual(found, {})


if __name__ == '__main__':
    unittest.main()
