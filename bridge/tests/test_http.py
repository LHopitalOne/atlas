import unittest

from atlas_bridge.core.http import (
    ANY,
    Extraction,
    PathTemplate,
    Route,
    methods_match,
    score,
    stretch_score,
    swallows_literals,
)


def p(path):
    return PathTemplate.parse(path)


class PathTemplateTest(unittest.TestCase):
    def test_parse_and_print(self):
        self.assertEqual(str(p('/rpc/{name}/{version}/')), '/rpc/{name}/{version}')
        self.assertEqual(str(p('//a//{*rest}?x=1')), '/a/{*rest}')
        self.assertEqual(str(p('/v{n}/Items')), '/v{n}/items')  # partly dynamic segment is a parameter
        self.assertEqual(p('/a/{b}/c').literals, 2)
        self.assertEqual(str(p('/')), '/')

    def test_score(self):
        self.assertEqual(score(p('/rpc/{a}/{b}'), p('/rpc/{name}/{version}')), 7)
        self.assertEqual(score(p('/rpc/x/{b}'), p('/rpc/{name}/{version}')), 6)
        self.assertIsNone(score(p('/{storage}'), p('/health')))  # shares no fixed word with the route
        self.assertIsNone(score(p('/a/b'), p('/a/c')))
        self.assertIsNone(score(p('/a/b'), p('/a')))
        self.assertIsNone(score(p('/a'), p('/a/b')))
        self.assertIsNone(score(p('/api/{id}/envelope'), p('/{org}/issues/{id}')))  # no fixed word in common
        self.assertEqual(score(p('/{a}/{b}'), p('/{x}/{y}')), 4)  # a route without fixed words needs none

    def test_wildcards(self):
        self.assertEqual(score(p('/proxy/a/b/c'), p('/proxy/{*path}')), 3)
        self.assertEqual(score(p('/api/{*rest}'), p('/api/x/y')), 3)

    def test_catch_all_that_swallows_literals(self):
        self.assertTrue(swallows_literals(p('/api/0/relays/metrics'), p('/{*path}')))
        self.assertTrue(swallows_literals(p('/api/{id}/envelope'), p('/api/relay/{*path}')))
        self.assertFalse(swallows_literals(p('/proxy/{path}'), p('/proxy/{*path}')))
        self.assertFalse(swallows_literals(p('/a/b'), p('/a/b')))

    def test_stretch(self):
        route = p('/{dataset}/{entity}/subscriptions/{partition}/{key}')
        self.assertIsNone(score(p('/{d}/{e}/subscriptions/{id}'), route))
        self.assertEqual(stretch_score(p('/{d}/{e}/subscriptions/{id}'), route), 9)
        self.assertIsNone(stretch_score(p('/{d}/{e}/subscriptions/x'), route))  # last segment is not a parameter
        self.assertIsNone(stretch_score(p('/{d}/{id}'), p('/{a}/b/{c}')))  # would swallow a literal
        self.assertIsNone(stretch_score(p('/a/{id}'), p('/a/{id}')))  # nothing to stretch
        self.assertIsNone(stretch_score(p('/x/{id}'), p('/a/{b}/{c}')))

    def test_methods(self):
        self.assertTrue(methods_match('POST', frozenset({'GET', 'POST'})))
        self.assertTrue(methods_match(ANY, frozenset({'GET'})))
        self.assertTrue(methods_match('delete', frozenset({ANY})))
        self.assertFalse(methods_match('DELETE', frozenset({'GET'})))

    def test_extend(self):
        a = Extraction([Route('r', 'f', 1, p('/a'))], [])
        a.extend(Extraction([Route('r', 'f', 2, p('/b'))], []))
        self.assertEqual(len(a.routes), 2)


if __name__ == '__main__':
    unittest.main()
