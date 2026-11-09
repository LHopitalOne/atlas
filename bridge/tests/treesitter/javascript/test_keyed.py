import unittest

from .support import Repository


def calls(files):
    return {(c.method, str(c.path)): c for c in Repository(files).extract().calls}


class KeyedRequestTest(unittest.TestCase):
    def test_swr_keys_are_get_requests(self):
        found = calls(
            {
                'pages/notes.js': "import useSWR from 'swr';\n"
                'export default function Notes({ id, query }) {\n'
                "  const { data } = useSWR('/api/notes');\n"
                '  const one = useSWR(id ? `/api/notes/${id}` : null, fetcher);\n'
                '  const key = query ? `/api/search?q=${query}` : null;\n'
                '  const hits = useSWR(key, { keepPreviousData: true });\n'
                "  const pair = useSWR(['/api/tags', token], ([url, t]) => get(url, t));\n"
                "  const later = useSWR(() => '/api/me');\n"
                '}\n',
                'lib/prefetch.ts': "import useSWRImmutable from 'swr/immutable';\nimport { preload } from 'swr';\n"
                "preload('/api/user', fetcher);\nexport const useFlags = () => useSWRImmutable('/api/flags');\n",
            }
        )
        self.assertEqual(
            sorted(found),
            [
                ('GET', '/api/flags'),
                ('GET', '/api/me'),
                ('GET', '/api/notes'),
                ('GET', '/api/notes/{id}'),
                ('GET', '/api/search'),
                ('GET', '/api/tags'),
                ('GET', '/api/user'),
            ],
        )
        notes = found[('GET', '/api/notes')]
        self.assertEqual((notes.file, notes.line, notes.function), ('pages/notes.js', 3, 'Notes'))

    def test_a_hook_of_the_repository_is_settled_at_its_callers(self):
        found = calls(
            {
                'lib/hooks.js': "import useSWR from 'swr';\nexport function useApi(path) { return useSWR(path); }\n",
                'pages/a.js': "import { useApi } from '../lib/hooks';\nexport const A = () => useApi('/api/orders');\n",
            }
        )
        self.assertEqual(sorted(found), [('GET', '/api/orders')])
        self.assertEqual(found[('GET', '/api/orders')].file, 'pages/a.js')

    def test_tanstack_query_keys_only_with_the_default_query_function(self):
        found = calls(
            {
                'src/q.ts': "import { useQuery } from '@tanstack/react-query';\n"
                "useQuery({ queryKey: ['/api/projects'] });\n"
                "useQuery({ queryKey: ['/api/own'], queryFn: () => load() });\n"
                "useQuery({ queryKey: ['todos'] });\n",
            }
        )
        self.assertEqual(sorted(found), [('GET', '/api/projects')])

    def test_keys_that_are_not_urls_or_not_from_the_library(self):
        found = calls(
            {
                'src/a.js': "import useSWR from 'swr';\nimport { useQuery } from './local';\n"
                "useSWR('user-settings');\nuseSWR(['todos', 1]);\nuseQuery({ queryKey: ['/api/x'] });\n",
                'src/b.js': "useSWR('/api/not-imported');\n",
            }
        )
        self.assertEqual(found, {})


if __name__ == '__main__':
    unittest.main()
