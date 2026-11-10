import unittest

from atlas_bridge.core.http import Protocol

from .support import Repository

INIT = (
    "import { initTRPC } from '@trpc/server';\n"
    'const t = initTRPC.context<Ctx>().create();\n'
    'export const createTRPCRouter = t.router;\n'
    'export const authed = t.procedure.use(auth);\n'
)
BILLING = (
    "import { z } from 'zod';\n"
    "import { createTRPCRouter, authed } from '../trpc';\n"
    'const refund = authed.input(z.string()).mutation(({ input }) => input);\n'
    'export const invoices = createTRPCRouter({\n'
    '  byId: authed.input(z.string()).query(({ input }) => null),\n'
    '  refund,\n'
    "  'void': authed.mutation(() => null),\n"
    '  admin: { purge: authed.mutation(() => 0) },\n'
    '  live: authed.subscription(() => null),\n'
    '});\n'
)
ROOT = (
    "import { createTRPCRouter } from './trpc';\n"
    "import { invoices } from './routers/invoices';\n"
    'export const appRouter = createTRPCRouter({ invoices, health: createTRPCRouter({ ping: x.query(() => 1) }) });\n'
)


def routes(files):
    return {(m, str(r.path)): r for r in Repository(files, 'api').extract().routes for m in r.methods}


class TrpcRoutesTest(unittest.TestCase):
    def files(self, server):
        return {'src/trpc.ts': INIT, 'src/routers/invoices.ts': BILLING, 'src/root.ts': ROOT, 'src/server.ts': server}

    def test_procedures_served_by_the_fetch_adapter(self):
        found = routes(
            self.files(
                "import { fetchRequestHandler } from '@trpc/server/adapters/fetch';\n"
                "import { appRouter } from './root';\n"
                'export const handler = (req) =>\n'
                "  fetchRequestHandler({ endpoint: '/api/trpc', req, router: appRouter });\n"
            )
        )
        self.assertEqual(
            sorted(found),
            [
                ('GET', '/api/trpc/health.ping'),
                ('GET', '/api/trpc/invoices.byid'),
                ('POST', '/api/trpc/invoices.admin.purge'),
                ('POST', '/api/trpc/invoices.refund'),
                ('POST', '/api/trpc/invoices.void'),
            ],
        )
        refund = found[('POST', '/api/trpc/invoices.refund')]
        self.assertEqual((refund.file, refund.line, refund.handler), ('src/routers/invoices.ts', 6, 'invoices.refund'))
        self.assertTrue(all(r.protocol == Protocol.HTTP for r in found.values()))

    def test_standalone_and_express_prefixes(self):
        standalone = routes(
            self.files(
                "import { createHTTPServer } from '@trpc/server/adapters/standalone';\n"
                "import { appRouter } from './root';\n"
                'createHTTPServer({ router: appRouter }).listen(3000);\n'
            )
        )
        self.assertIn(('GET', '/health.ping'), standalone)
        express = routes(
            self.files(
                "import * as trpcExpress from '@trpc/server/adapters/express';\n"
                "import { createExpressMiddleware } from '@trpc/server/adapters/express';\n"
                "import { appRouter } from './root';\n"
                "app.use('/rpc', createExpressMiddleware({ router: appRouter }));\n"
            )
        )
        self.assertIn(('GET', '/rpc/health.ping'), express)

    def test_unknown_prefix_or_router_serves_nothing(self):
        found = routes(
            self.files(
                "import { createExpressMiddleware } from '@trpc/server/adapters/express';\n"
                "import { fetchRequestHandler } from '@trpc/server/adapters/fetch';\n"
                "import { appRouter } from './root';\n"
                'export const mw = createExpressMiddleware({ router: appRouter });\n'
                'fetchRequestHandler({ endpoint: process.env.PREFIX, router: appRouter });\n'
                "fetchRequestHandler({ endpoint: '/x', router: { ping: x.query(() => 1) } });\n"
            )
        )
        self.assertEqual(found, {})


LINK = (
    "import { createTRPCClient, httpBatchLink, splitLink, wsLink } from '@trpc/client';\n"
    'export const api = createTRPCClient<AppRouter>({\n'
    '  links: [splitLink({ condition: (op) => op.type === "subscription", true: wsLink({ client }),\n'
    '    false: httpBatchLink({ url: `${process.env.BILLING_URL}/api/trpc` }) })],\n'
    '});\n'
)


def calls(files):
    return {(c.method, str(c.path)): c for c in Repository(files, 'web').extract().calls}


class TrpcCallsTest(unittest.TestCase):
    def test_procedure_calls_on_an_imported_client(self):
        found = calls(
            {
                'src/lib/api.ts': LINK,
                'src/pages/invoice.ts': "import { api } from '@/lib/api';\n"
                'export const load = (id) => api.invoices.byId.query(id);\n'
                'export async function refund(id) { return api.invoices.refund.mutate(id); }\n'
                'export const purge = () => api.invoices.admin.purge.mutate();\n',
            }
        )
        self.assertEqual(
            sorted(found),
            [
                ('GET', '/api/trpc/invoices.byid'),
                ('POST', '/api/trpc/invoices.admin.purge'),
                ('POST', '/api/trpc/invoices.refund'),
            ],
        )
        call = found[('GET', '/api/trpc/invoices.byid')]
        self.assertIn('BILLING_URL', call.hints)
        self.assertEqual((call.file, call.line, call.function), ('src/pages/invoice.ts', 2, 'load'))

    def test_method_override_sends_queries_as_post(self):
        found = calls(
            {
                'src/a.ts': "import { createTRPCProxyClient, httpLink } from '@trpc/client';\n"
                'const c = createTRPCProxyClient({\n'
                "  links: [httpLink({ url: 'http://billing/trpc', methodOverride: 'POST' })],\n"
                '});\n'
                'c.ping.query();\n'
            }
        )
        self.assertEqual(sorted(found), [('POST', '/trpc/ping')])

    def test_other_query_calls_and_unclear_clients_send_nothing(self):
        found = calls(
            {
                'src/a.ts': "import { createTRPCClient, httpLink } from '@trpc/client';\n"
                "import { Pool } from 'pg';\n"
                'const pool = new Pool();\n'
                "pool.users.query('select 1');\n"
                "const two = createTRPCClient({ links: [httpLink({ url: '/a' }), httpLink({ url: '/b' })] });\n"
                'two.ping.query();\n'
                'function f(client) { return client.ping.query(); }\n'
            }
        )
        self.assertEqual(found, {})


if __name__ == '__main__':
    unittest.main()
