import unittest

from atlas_bridge.adapters.treesitter.rust.routes.paths import RoutePath
from atlas_bridge.adapters.treesitter.rust.values import UrlPiece


class RoutePathTest(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(RoutePath.canonical('/a/:id/*rest'), '/a/{id}/{*rest}')
        self.assertEqual(RoutePath.canonical('/a/{id:\\d+}/{tail}*'), '/a/{id}/{*tail}')
        self.assertEqual(RoutePath.canonical('/a/{x:y}*/{*}/*/{a*b:c}'), '/a/{*x}/{*}/*/{a*b:c}')

    def test_join(self):
        self.assertEqual(RoutePath.join('/api/', '/'), '/api')
        self.assertEqual(RoutePath.join('/', '/x'), '/x')
        self.assertEqual(RoutePath.join('/', '/'), '/')


class UrlPieceTest(unittest.TestCase):
    def test_path_like(self):
        self.assertTrue(UrlPiece.path_like('/x'))
        self.assertTrue(UrlPiece.path_like('http://h'))
        self.assertTrue(UrlPiece.path_like('{base}/x'))
        self.assertFalse(UrlPiece.path_like('{base}x'))
        self.assertFalse(UrlPiece.path_like('relative'))

    def test_param_skips_conversions(self):
        self.assertEqual(UrlPiece.param('&id.to_string()'), 'id')
        self.assertEqual(UrlPiece.param('self.project.clone()'), 'project')
        self.assertEqual(UrlPiece.param('clone()'), 'clone')
        self.assertEqual(UrlPiece.param(''), 'param')


if __name__ == '__main__':
    unittest.main()
