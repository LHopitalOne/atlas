import unittest

from atlas_bridge.core.http import ANY, Extraction, PathTemplate, Route


def p(path):
    return PathTemplate.parse(path)


class PathTemplateTest(unittest.TestCase):
    def test_parse_and_print(self):
        self.assertEqual(str(p('/rpc/{name}/{version}/')), '/rpc/{name}/{version}')
        self.assertEqual(str(p('//a//{*rest}?x=1')), '/a/{*rest}')
        self.assertEqual(str(p('/v{n}/Items')), '/v{n}/items')  # partly dynamic segment is a parameter
        self.assertEqual(p('/a/{b}/c').literals, 2)
        self.assertEqual(str(p('/')), '/')

    def test_fit(self):
        self.assertEqual(p('/rpc/{a}/{b}').fit(p('/rpc/{name}/{version}')), 7)
        self.assertEqual(p('/rpc/x/{b}').fit(p('/rpc/{name}/{version}')), 6)
        self.assertIsNone(p('/{storage}').fit(p('/health')))  # shares no fixed word with the route
        self.assertIsNone(p('/a/b').fit(p('/a/c')))
        self.assertIsNone(p('/a/b').fit(p('/a')))
        self.assertIsNone(p('/a').fit(p('/a/b')))
        self.assertIsNone(p('/api/{id}/envelope').fit(p('/{org}/issues/{id}')))  # no fixed word in common
        self.assertEqual(p('/{a}/{b}').fit(p('/{x}/{y}')), 4)  # a route without fixed words needs none

    def test_wildcards(self):
        self.assertEqual(p('/proxy/a/b/c').fit(p('/proxy/{*path}')), 3)
        self.assertEqual(p('/api/{*rest}').fit(p('/api/x/y')), 3)

    def test_catch_all_that_swallows_literals(self):
        self.assertTrue(p('/api/0/relays/metrics').swallowed_by(p('/{*path}')))
        self.assertTrue(p('/api/{id}/envelope').swallowed_by(p('/api/relay/{*path}')))
        self.assertFalse(p('/proxy/{path}').swallowed_by(p('/proxy/{*path}')))
        self.assertFalse(p('/a/b').swallowed_by(p('/a/b')))

    def test_stretch(self):
        route = p('/{dataset}/{entity}/subscriptions/{partition}/{key}')
        self.assertIsNone(p('/{d}/{e}/subscriptions/{id}').fit(route))
        self.assertEqual(p('/{d}/{e}/subscriptions/{id}').stretch_fit(route), 9)
        self.assertIsNone(p('/{d}/{e}/subscriptions/x').stretch_fit(route))  # last segment is not a parameter
        self.assertIsNone(p('/{d}/{id}').stretch_fit(p('/{a}/b/{c}')))  # would swallow a literal
        self.assertIsNone(p('/a/{id}').stretch_fit(p('/a/{id}')))  # nothing to stretch
        self.assertIsNone(p('/x/{id}').stretch_fit(p('/a/{b}/{c}')))

    def test_methods(self):
        self.assertTrue(Route('r', 'f', 1, p('/'), frozenset({'GET', 'POST'})).accepts('POST'))
        self.assertTrue(Route('r', 'f', 1, p('/'), frozenset({'GET'})).accepts(ANY))
        self.assertTrue(Route('r', 'f', 1, p('/'), frozenset({ANY})).accepts('delete'))
        self.assertFalse(Route('r', 'f', 1, p('/'), frozenset({'GET'})).accepts('DELETE'))

    def test_empty_path_is_still_a_path(self):
        self.assertTrue(p('/'))  # an empty template must not be falsy: callers test `if call.path`
        self.assertEqual(p('/').size, 0)

    def test_extend(self):
        a = Extraction([Route('r', 'f', 1, p('/a'))], [])
        a.extend(Extraction([Route('r', 'f', 2, p('/b'))], []))
        self.assertEqual(len(a.routes), 2)


if __name__ == '__main__':
    unittest.main()
