import unittest

from atlas_bridge.core.http import Call, Extraction, PathTemplate, Route
from atlas_bridge.core.model import Status
from atlas_bridge.usecases.bases import BaseHints, PrefixOrder
from atlas_bridge.usecases.link import LinkFinder

P = PathTemplate.parse


class PathShapesTest(unittest.TestCase):
    def test_prefixed_fit(self):
        fit = P('/courses/{id}').prefixed_fit(P('/api/v1/courses/{pk}'), 3)
        self.assertEqual((fit[0], str(fit[1])), (5, '/api/v1'))
        self.assertIsNone(P('/courses/{id}').prefixed_fit(P('/tagging/courses/{pk}'), 3))  # not an API prefix
        self.assertIsNone(P('/courses').prefixed_fit(P('/api/a/b/c/courses'), 3))  # too long a prefix
        self.assertIsNone(P('/{id}').prefixed_fit(P('/api/v1/{pk}'), 3))  # nothing fixed to go on
        self.assertIsNone(P('/a/x').prefixed_fit(P('/api/{v}/a/x'), 3))  # the prefix must be fixed
        self.assertIsNone(P('/search/{id}').prefixed_fit(P('/api/{id}/{*rest}'), 3))
        self.assertIsNone(P('/a/x/b').prefixed_fit(P('/api/a/{*rest}'), 3))  # the catch-all swallows 'b'

    def test_api_paths(self):
        self.assertTrue(P('/api/0/x').is_api)
        self.assertTrue(P('/v2/grades').is_api)
        self.assertFalse(P('/version/x').is_api)

    def test_routes_of_parameters_only(self):
        self.assertIsNone(P('/accounts').fit(P('/{slug}')))  # a fallback, not a route for /accounts
        self.assertIsNotNone(P('/{storage}').fit(P('/{storage}')))
        self.assertIsNotNone(P('/x/y').fit(P('/{*rest}')))

    def test_partly_literal_segments(self):
        self.assertIsNone(P('/{name}').fit(P('/swagger.{format}')))
        self.assertIsNotNone(P('/swagger.json').fit(P('/swagger.{format}')))
        self.assertIsNotNone(P('/b/{u},{k}').fit(P('/b/{username},{usage_key}')))
        self.assertIsNone(P('/b/{u}-{k}').fit(P('/b/{username},{usage_key}')))


class BaseHintsTest(unittest.TestCase):
    def test_reads_only_code_expressions(self):
        self.assertTrue(BaseHints({'get_catalog_api_base_url()'}).names_an_api())
        self.assertFalse(BaseHints({'src/data/api.js', 'Calls the api.'}).names_an_api())

    def test_mentions(self):
        hints = BaseHints({'partner.lms_coursemode_api_url', "partner.lms_coursemode_api_url.rstrip('/')"})
        self.assertEqual(hints.mentions(P('/api/course_modes/v1')), 1)
        self.assertEqual(hints.mentions(P('/api/commerce/v1')), 0)


class PrefixedLinksTest(unittest.TestCase):
    ROUTES = [
        Route('lms', 'urls.py', 1, P('/courses/{course_id}')),  # a page whose path fits exactly
        Route('lms', 'urls.py', 2, P('/api/course_modes/v1/courses/{course_id}')),
        Route('lms', 'urls.py', 3, P('/api/commerce/v1/courses/{course_id}')),
        Route('lms', 'urls.py', 4, P('/v1/courses/{course_id}')),
        Route('catalog', 'urls.py', 5, P('/api/v1/programs/{uuid}')),
    ]

    def links(self, path, hints, method='GET'):
        call = Call('discovery', 'a.py', 1, P(path), method, hints=frozenset(hints))
        found = LinkFinder(['lms', 'catalog', 'discovery']).find(Extraction(list(self.ROUTES), [call]))
        return [(str(lk.route.path), lk.status, lk.reason) for lk in found if lk.route]

    def test_an_api_base_prefers_the_api_route_its_name_mentions(self):
        found = self.links('/courses/{key}', ['partner.lms_coursemode_api_url'])
        route, reason = '/api/course_modes/v1/courses/{course_id}', 'fits if the base URL ends in /api/course_modes/v1'
        self.assertEqual(found, [(route, Status.INFERRED, reason)])

    def test_without_an_api_base_the_exact_route_wins(self):
        self.assertEqual(self.links('/courses/{key}', ['lms_url'])[0][:2], ('/courses/{course_id}', Status.MATCHED))

    def test_a_prefix_only_when_nothing_fits_exactly(self):
        found = self.links('/programs/{uuid}', ['catalog_client'])
        self.assertEqual(found[0][:2], ('/api/v1/programs/{uuid}', Status.INFERRED))

    def test_the_same_route_in_several_api_versions_is_taken_in_the_newest(self):
        versions = [Route('catalog', 'urls.py', 6, P(f'/api/{v}/search/{{q}}')) for v in ('v3', 'v10', 'v4')]
        call = Call('discovery', 'a.py', 1, P('/search/{q}'), 'GET', hints=frozenset({'catalog_client'}))
        (link,) = LinkFinder(['catalog', 'discovery']).find(Extraction(versions, [call]))
        self.assertEqual((str(link.route.path), link.status), ('/api/v10/search/{q}', Status.INFERRED))


class PrefixOrderTest(unittest.TestCase):
    def test_versions_of_one_base_newest_first_anything_else_by_text(self):
        order = sorted(['/api/v3', '/api/v5', '/api/v4', '/api', '/api/beta'], key=PrefixOrder.key)
        self.assertEqual(order, ['/api', '/api/beta', '/api/v5', '/api/v4', '/api/v3'])


if __name__ == '__main__':
    unittest.main()
