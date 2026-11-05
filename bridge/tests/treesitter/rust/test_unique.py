import unittest

from atlas_bridge.adapters.treesitter.rust.routes import UniqueRoutes
from atlas_bridge.core.http import PathTemplate, Route


def route(line, path='/a', handler='h', file='f.rs'):
    return Route('svc', file, line, PathTemplate.parse(path), frozenset({'GET'}), handler, framework='axum')


class UniqueRoutesTest(unittest.TestCase):
    def test_first_found_wins(self):
        self.assertEqual([r.line for r in UniqueRoutes.first([route(67), route(59)])], [67])
        self.assertEqual([r.line for r in UniqueRoutes.first([route(59), route(67)])], [59])

    def test_trailing_slash_variants_are_the_same_route(self):
        self.assertEqual([r.line for r in UniqueRoutes.first([route(2, '/a/'), route(1, '/a')])], [2])

    def test_different_handlers_files_or_paths_are_kept_in_order(self):
        routes = [route(3), route(2, handler='g'), route(1, file='g.rs'), route(4, '/b')]
        self.assertEqual(UniqueRoutes.first(routes), routes)


if __name__ == '__main__':
    unittest.main()
