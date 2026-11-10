import unittest

from .support import Repository

calls = Repository.calls


class EventSourceTest(unittest.TestCase):
    def test_an_event_source_is_a_get_of_its_url(self):
        found = calls(
            "const BASE = import.meta.env.VITE_API ?? 'http://api:8000';\n"
            'export function watch(id) {\n'
            '  const source = new EventSource(`${BASE}/orders/${id}/events`, { withCredentials: true });\n'
            "  source.addEventListener('status', () => {});\n"
            '}\n'
            "export const feed = new window.EventSource('/api/feed');\n",
            path='src/a.ts',
        )
        self.assertEqual(sorted(found), [('GET', '/api/feed'), ('GET', '/orders/{id}/events')])
        self.assertEqual(found[('GET', '/orders/{id}/events')].line, 3)

    def test_url_from_a_wrapper_parameter(self):
        found = calls(
            'class Live {\n'
            '  open(path) { return new EventSource(`${this.base}${path}`); }\n'
            "  ticks() { return this.open('/stream/ticks'); }\n"
            '}\n'
        )
        self.assertEqual(sorted(found), [('GET', '/stream/ticks')])

    def test_another_class_named_like_it_is_not_one_without_a_url(self):
        self.assertEqual(calls('const s = new EventSource();\nconst t = new Other.Source(url);\n'), {})


if __name__ == '__main__':
    unittest.main()
