import unittest

from .support import Repository


def found(files):
    return sorted((c.method, str(c.path), c.file, c.line) for c in Repository(files).extract().calls)


class MethodReturnTest(unittest.TestCase):
    def test_url_a_method_of_a_repository_class_returns(self):
        calls = found(
            {
                'src/client.ts': 'export class Api {\n'
                '  constructor(private readonly base: string) {}\n'
                "  feedUrl(): URL { return new URL('/v1/feed', this.base); }\n"
                "  label(): string { return 'feed'; }\n"
                '}\n',
                'src/main.ts': "import { Api } from './client';\n"
                "const api = new Api('http://api:8000');\n"
                'fetch(api.feedUrl());\n'
                'export const typed = (a: Api) => fetch(a.feedUrl());\n'
                'fetch(api.label());\n'  # not a URL
                'export const other = (o: Other) => fetch(o.feedUrl());\n',  # not a class of the repository
            }
        )
        self.assertEqual(calls, [('GET', '/v1/feed', 'src/main.ts', 3), ('GET', '/v1/feed', 'src/main.ts', 4)])


class ConstructorFieldTest(unittest.TestCase):
    def test_a_field_set_from_the_constructor_is_settled_where_the_class_is_made(self):
        calls = found(
            {
                'src/feed.ts': 'export class Feed {\n'
                '  private readonly url: string;\n'
                '  constructor(url: string, private readonly base: string) { this.url = url; }\n'
                '  open() { return fetch(this.url); }\n'
                '  more() { return fetch(`${this.base}/more`); }\n'
                '}\n',
                'src/main.ts': "import { Feed } from './feed';\n"
                "const BASE = 'http://feeds:9000';\n"
                'new Feed(`${BASE}/v1/stream`, BASE).open();\n'
                'export function make(u: string) { return new Feed(u, BASE); }\n'
                "make('/v2/stream');\n",
            }
        )
        self.assertEqual(
            calls,
            [
                ('GET', '/more', 'src/feed.ts', 5),
                ('GET', '/v1/stream', 'src/main.ts', 3),
                ('GET', '/v2/stream', 'src/main.ts', 5),
            ],
        )

    def test_a_field_the_constructor_computes_is_not_settled(self):
        calls = found(
            {
                'src/feed.ts': 'export class Feed {\n'
                '  private readonly url: string;\n'
                '  constructor(id: string) { this.url = lookup(id); }\n'
                '  open() { return fetch(this.url); }\n'
                '}\n'
                "new Feed('/v1/x');\n",
            }
        )
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
