import unittest

from atlas_bridge.core.http import ANY

from .support import Repository

routes = Repository.routes


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

    def test_routers_made_by_factories_and_fastify_plugins(self):
        found = routes(
            {
                'src/server.ts': "import { adminRouter } from './routes/admin';\n"
                "import { apiRoutes } from './routes/api';\n"
                'const app = express();\n'
                "app.use('/admin', adminRouter(bank));\n"
                "app.use('/local', localRouter());\n"
                "app.use('/unknown', makeIt());\n"
                'const fastify = Fastify();\n'
                "fastify.register(apiRoutes, { prefix: '/api' });\n"
                'fastify.register(cors);\n'
                'function localRouter() {\n'
                '  const r = Router();\n'
                "  r.get('/l', l);\n"
                '  return r;\n'
                '}\n',
                'src/routes/admin.ts': 'export function adminRouter(bank) {\n'
                '  const router = Router();\n'
                "  router.post('/questions', (req, res) => res.json(bank));\n"
                '  return router;\n'
                '}\n',
                'src/routes/api.ts': "export const apiRoutes = async (app) => {\n  app.post('/orders', create);\n};\n",
            }
        )
        self.assertEqual(sorted(found), [('GET', '/local/l'), ('POST', '/admin/questions'), ('POST', '/api/orders')])


if __name__ == '__main__':
    unittest.main()
