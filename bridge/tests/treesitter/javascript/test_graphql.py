import unittest

from atlas_bridge.adapters.treesitter.javascript.calls.graphql.document import GraphqlDocument, Operation
from atlas_bridge.core.http import ANY, Protocol

from .support import Repository

QUERIES = (
    'const FIELDS = `\n  fragment RoomFields on Room { id name }\n`;\n'
    'export const ROOMS = `\n  ${FIELDS}\n  query Rooms($city: String) {\n'
    '    rooms(city: $city) { ...RoomFields }\n  }\n`;\n'
    'export const BOOK = `\n  mutation BookRoom($input: BookInput!) { bookRoom(input: $input) { id } }\n`;\n'
)
CLIENT = (
    "import { API_URL } from '../config';\n"
    'export async function gql(query, variables = {}) {\n'
    '  const res = await fetch(`${API_URL}/graphql`, {\n'
    "    method: 'POST',\n"
    '    body: JSON.stringify({ query, variables }),\n'
    '  });\n'
    '  return res.json();\n'
    '}\n'
)


def calls(files):
    return {(c.protocol, c.method, str(c.path)): c for c in Repository(files).extract().calls}


class DocumentTest(unittest.TestCase):
    def test_operations_and_their_root_fields(self):
        text = (
            'fragment F on Booking { id }\n'
            '# a comment { not a field }\n'
            'query GetBooking($id: ID!) { booking(id: $id) { ...F payment { id } } __typename }\n'
            'mutation { a: cancelBooking(id: "1}") @include(if: $x) { id } ... on Mutation { other } ...Spread }\n'
            '{ me }\n'
        )
        self.assertEqual(
            GraphqlDocument(text).operations(),
            [
                Operation('query', 'GetBooking', ('booking',)),
                Operation('mutation', '', ('cancelBooking',)),
                Operation('query', '', ('me',)),
            ],
        )

    def test_text_that_is_not_a_document(self):
        for text in (
            'rooms near me',
            'query string here',
            '{"a": 1}',
            'SELECT * FROM rooms',
            '',
            '{ __schema { types } }',
        ):
            self.assertEqual(GraphqlDocument(text).operations(), [], text)


class GraphqlCallTest(unittest.TestCase):
    def test_documents_given_to_a_helper_that_posts_them(self):
        found = calls(
            {
                'src/config.ts': "export const API_URL = 'http://127.0.0.1:4000';\n",
                'src/api/queries.ts': QUERIES,
                'src/api/client.ts': CLIENT,
                'src/api/rooms.ts': "import { gql } from './client';\nimport { ROOMS, BOOK } from './queries';\n"
                'export const listRooms = (city) => gql(ROOMS, { city });\n'
                'export async function book(input) { return gql(BOOK, { input }); }\n',
            }
        )
        self.assertEqual(sorted(found), [(Protocol.GRAPHQL, ANY, '/bookroom'), (Protocol.GRAPHQL, ANY, '/rooms')])
        rooms = found[(Protocol.GRAPHQL, ANY, '/rooms')]
        self.assertEqual((rooms.file, rooms.line, rooms.function), ('src/api/rooms.ts', 3, 'listRooms'))
        self.assertTrue({'gql', 'Rooms', '127.0.0.1'} <= rooms.hints)

    def test_a_document_written_at_the_request(self):
        found = calls(
            {
                'src/a.js': 'const Q = gql`query { orders { id } }`;\n'
                "axios.post('/graphql', { query: Q });\n"
                "const body = JSON.stringify({ query: 'mutation { ship(id: 1) }' });\n"
                "fetch('/api/graphql', { method: 'POST', body });\n"
            }
        )
        self.assertEqual(sorted(found), [(Protocol.GRAPHQL, ANY, '/orders'), (Protocol.GRAPHQL, ANY, '/ship')])

    def test_a_json_query_that_is_not_graphql_stays_a_post(self):
        found = calls(
            {
                'src/a.js': "fetch('/api/search', { method: 'POST', body: JSON.stringify({ query: 'red shoes' }) });\n"
                "export function search(query) { return axios.post('/api/find', { query }); }\n"
                "search('blue hats');\n"
            }
        )
        self.assertEqual(sorted(found), [(Protocol.HTTP, 'POST', '/api/find'), (Protocol.HTTP, 'POST', '/api/search')])

    def test_graphql_client_entry_points(self):
        found = calls(
            {
                'src/docs.ts': "import { gql } from '@apollo/client';\n"
                'export const GET_DOGS = gql`\n  query GetDogs { dogs { id } }\n`;\n',
                'src/Dogs.tsx': "import { useQuery, useMutation } from '@apollo/client';\n"
                "import { useQuery as useUrql } from 'urql';\n"
                "import { request } from 'graphql-request';\n"
                "import { GET_DOGS } from './docs';\n"
                'export function Dogs() {\n'
                '  useQuery(GET_DOGS);\n'
                '  useMutation(gql`mutation AddDog { addDog { id } }`);\n'
                '  useUrql({ query: `query { cats { id } }` });\n'
                "  request('/graphql', `{ birds { id } }`);\n"
                '}\n',
            }
        )
        paths = sorted(p for _, _, p in found)
        self.assertEqual(paths, ['/adddog', '/birds', '/cats', '/dogs'])
        self.assertIn('@apollo/client', found[(Protocol.GRAPHQL, ANY, '/dogs')].hints)


if __name__ == '__main__':
    unittest.main()
