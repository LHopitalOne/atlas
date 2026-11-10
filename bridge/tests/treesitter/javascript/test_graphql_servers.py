import unittest

from atlas_bridge.core.http import ANY, Protocol

from .support import Repository


def calls(files):
    return {(c.protocol, str(c.path)): c for c in Repository(files).extract().calls}


def routes(files):
    return {(r.protocol, str(r.path)): r for r in Repository(files).extract().routes}


CLIENT = (
    "import { GraphQLClient } from 'graphql-request';\n"
    "export const shop = new GraphQLClient(process.env.SHOP_GRAPHQL ?? 'http://shop:4000/graphql');\n"
)


class ClientObjectTest(unittest.TestCase):
    def test_a_graphql_request_client_made_in_another_file(self):
        found = calls(
            {
                'src/client.ts': CLIENT,
                'src/orders.ts': "import { gql } from 'graphql-request';\n"
                "import { shop } from './client';\n"
                'const ORDERS = gql`query Orders { orders { id } }`;\n'
                'export const orders = () => shop.request<{ orders: [] }>(ORDERS);\n'
                'export const cancel = (id) => shop.request({ document: `mutation { cancelOrder { id } }` });\n'
                "export const raw = () => shop.rawRequest('{ customers { id } }');\n",
            }
        )
        self.assertEqual(sorted(p for _, p in found), ['/cancelorder', '/customers', '/orders'])
        self.assertTrue(all(c.protocol == Protocol.GRAPHQL and c.method == ANY for c in found.values()))

    def test_apollo_client_methods(self):
        found = calls(
            {
                'src/apollo.js': "import { ApolloClient, InMemoryCache, gql } from '@apollo/client';\n"
                "const client = new ApolloClient({ uri: '/graphql', cache: new InMemoryCache() });\n"
                'client.query({ query: gql`query { me { id } }` });\n'
                'client.mutate({ mutation: gql`mutation { logout }` });\n',
            }
        )
        self.assertEqual(sorted(p for _, p in found), ['/logout', '/me'])

    def test_request_on_another_object_is_not_graphql(self):
        found = calls(
            {
                'src/db.js': "import { Pool } from 'pg';\n"
                'const pool = new Pool();\n'
                "export const q = () => pool.query('{ items { id } }');\n"
                "export const r = (api) => api.request('{ stars { id } }');\n",
            }
        )
        self.assertFalse([p for p in found if p[0] == Protocol.GRAPHQL])


RESOLVERS = (
    "import { createSchema } from 'graphql-yoga';\n"
    "import { reviewResolvers } from './reviews';\n"
    'const Query = {\n'
    '  products: () => [],\n'
    "  'product': (_p, { id }) => null,\n"
    '};\n'
    'export const schema = createSchema({\n'
    '  typeDefs,\n'
    '  resolvers: {\n'
    '    Query: { ...Query, ...reviewResolvers.Query },\n'
    '    Mutation: {\n'
    '      async addProduct(_p, args) { return args; },\n'
    '    },\n'
    '    Product: { price: (p) => p.cents / 100 },\n'
    '  },\n'
    '});\n'
)
REVIEWS = 'export const reviewResolvers = {\n  Query: {\n    reviews: () => [],\n  },\n};\n'


class ResolverMapTest(unittest.TestCase):
    def test_root_fields_of_a_yoga_schema_with_spreads_and_imports(self):
        found = routes({'src/schema.ts': RESOLVERS, 'src/reviews.ts': REVIEWS})
        self.assertEqual(
            {(p, r.file, r.line, r.handler) for (_, p), r in found.items()},
            {
                ('/products', 'src/schema.ts', 4, 'Query.products'),
                ('/product', 'src/schema.ts', 5, 'Query.product'),
                ('/addproduct', 'src/schema.ts', 12, 'Mutation.addProduct'),
                ('/reviews', 'src/reviews.ts', 3, 'Query.reviews'),
            },
        )
        self.assertTrue(all(r.protocol == Protocol.GRAPHQL for r in found.values()))

    def test_apollo_server_and_an_array_of_maps(self):
        found = routes(
            {
                'src/server.js': "import { ApolloServer } from '@apollo/server';\n"
                "import { makeExecutableSchema } from '@graphql-tools/schema';\n"
                'const a = { Query: { one: () => 1 } };\n'
                'const b = { Subscription: { ticks: { subscribe: () => null } } };\n'
                'new ApolloServer({ typeDefs, resolvers: { Query: { two: () => 2 } } });\n'
                'makeExecutableSchema({ typeDefs, resolvers: [a, b] });\n'
            }
        )
        self.assertEqual(sorted(p for _, p in found), ['/one', '/ticks', '/two'])

    def test_a_resolver_map_no_schema_builder_takes_serves_nothing(self):
        found = routes(
            {'src/x.js': "import { createSchema } from 'other';\ncreateSchema({ resolvers: { Query: { a: 1 } } });\n"}
        )
        self.assertEqual(found, {})


if __name__ == '__main__':
    unittest.main()
