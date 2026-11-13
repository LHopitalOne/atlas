import unittest

from .support import extract, requests_, routes


class SettingUrlsTest(unittest.TestCase):
    def test_urls_settings_name(self):
        ex = extract(
            {
                'proj/envs/devstack.py': """
                COURSE_CATALOG_URL_ROOT = 'http://edx.devstack.discovery:18381'
                COURSE_CATALOG_API_URL = f'{COURSE_CATALOG_URL_ROOT}/api/v1'
                JWT_AUTH = {'JWT_ISSUER': 'http://localhost:18000/oauth2', 'JWT_LEEWAY': 1}
                PAGE_SIZE = 20
                """,
                'proj/envs/test.py': "LMS_ROOT_URL = 'http://localhost:9999'\n",
                'tests/conftest.py': "SERVICE_URL = 'http://localhost:1'\n",
            }
        )
        found = sorted((u.name, u.address, str(u.path)) for u in ex.urls)
        self.assertEqual(
            found,
            [
                ('COURSE_CATALOG_API_URL', 'edx.devstack.discovery:18381', '/api/v1'),
                ('COURSE_CATALOG_URL_ROOT', 'edx.devstack.discovery:18381', '/'),
                ('JWT_ISSUER', 'localhost:18000', '/oauth2'),
            ],
        )


class SettingsValuesTest(unittest.TestCase):
    def test_settings_names_and_mappings(self):
        ex = extract(
            {
                'proj/settings/base.py': """
                LMS_URL = 'http://lms:8000'
                LMS_API_URLS = {'blocks': 'api/courses/v1/blocks/', 'meta': 'api/meta/'}
                """,
                'proj/settings/test.py': "LMS_URL = 'http://testserver'\n",
                'proj/client.py': """
                from urllib.parse import urljoin
                from django.conf import settings

                def blocks(session):
                    return session.get(urljoin(settings.LMS_URL, settings.LMS_API_URLS['blocks']))

                def unknown_key(session):
                    return session.get(settings.LMS_URL + settings.LMS_API_URLS[key])
                """,
            }
        )
        self.assertIn(('GET', '/api/courses/v1/blocks'), requests_(ex))
        call = next(c for c in ex.calls if str(c.path) == '/api/courses/v1/blocks')
        self.assertIn('lms', call.hints)  # the host of the setting's value
        self.assertIn("settings.LMS_API_URLS['blocks']", call.hints)


class HelperReturnsTest(unittest.TestCase):
    def test_functions_and_methods_that_return_a_url(self):
        ex = extract(
            {
                'svc/studio.py': """
                from urllib.parse import urljoin

                def course_url(key):
                    return f'/api/courses/{key}/'

                class StudioAPI:
                    def _make_url(self, path):
                        return urljoin(self._url, 'api/v1/' + path)

                    def _request(self, method, path, **kwargs):
                        url = self._make_url(path)
                        return self._api.request(method, url, **kwargs)

                    def rerun(self, key):
                        self._request('post', f'course_runs/{key}/rerun/')

                    def create(self):
                        self._request('post', 'course_runs/')

                def get_course(session, key):
                    return session.get(course_url(key))

                def two_returns(flag):
                    if flag:
                        return '/a/'
                    return '/b/'

                def get_either(session):
                    return session.get(two_returns(True))
                """,
            }
        )
        found = requests_(ex)
        self.assertIn(('POST', '/api/v1/course_runs/{key}/rerun'), found)
        self.assertIn(('POST', '/api/v1/course_runs'), found)
        self.assertIn(('GET', '/api/courses/{key}'), found)
        self.assertFalse(any(path in ('/a', '/b') for _, path in found))  # several returns: not followed


class DrfRouterTest(unittest.TestCase):
    def test_registered_viewsets_and_actions(self):
        ex = extract(
            {
                'proj/settings.py': "ROOT_URLCONF = 'proj.urls'\n",
                'proj/urls.py': """
                from django.urls import include, path
                from proj import api_urls
                urlpatterns = [path('api/v1/', include('proj.api_urls'))]
                """,
                'proj/api_urls.py': """
                from rest_framework import routers
                from proj.views import CourseRunViewSet

                router = routers.SimpleRouter()
                router.register(r'course_runs', CourseRunViewSet, basename='course_run')
                router.register(prefix=r'^catalogs', viewset=CatalogViewSet)
                other.register(r'ignored', IgnoredViewSet)
                urlpatterns = []
                urlpatterns += router.urls
                """,
                'proj/views.py': """
                from rest_framework.decorators import action

                class CourseRunViewSet:
                    @action(detail=True, methods=['post'], url_path='rerun')
                    def rerun(self, request, pk=None): ...

                    @action(detail=False)
                    def contains(self, request): ...

                    @staticmethod
                    def helper(): ...
                """,
            }
        )
        self.assertEqual(
            routes(ex),
            {
                ('/api/v1/course_runs', ('ANY',)),
                ('/api/v1/course_runs/{pk}', ('ANY',)),
                ('/api/v1/course_runs/{pk}/rerun', ('POST',)),
                ('/api/v1/course_runs/contains', ('GET',)),
                ('/api/v1/catalogs', ('ANY',)),
                ('/api/v1/catalogs/{pk}', ('ANY',)),
            },
        )

    def test_imported_and_nested_routers_in_lists_a_versioning_function_mounts(self):
        ex = extract(
            {
                'proj/settings.py': "ROOT_URLCONF = 'proj.urls'\n",
                'proj/urls.py': """
                from django.urls import include, re_path
                urlpatterns = [re_path(r'^api/', include('proj.api.urls'))]
                """,
                'proj/api/urls.py': """
                from django.urls import include, re_path
                from proj.accounts.urls import accounts_v5
                from proj.ratings.api_urls import ratings

                def versioned(version, url_patterns):
                    route_pattern = rf'^{version}/'
                    routes = url_patterns
                    return (re_path(route_pattern, include((routes, version))),)

                v5_urls = [
                    re_path(r'^accounts/', include(accounts_v5)),
                    re_path(r'^ratings/', include(ratings.urls)),
                ]
                urlpatterns = [*versioned('v5', v5_urls)]
                """,
                'proj/ratings/api_urls.py': """
                from rest_framework.routers import SimpleRouter
                ratings = SimpleRouter()
                ratings.register(r'rating', RatingViewSet)
                """,
                'proj/accounts/urls.py': """
                from django.urls import include, re_path
                from rest_framework_nested.routers import NestedSimpleRouter
                accounts = SimpleRouter()
                accounts.register(r'account', AccountViewSet)
                collections = NestedSimpleRouter(accounts, r'account', lookup='user')
                collections.register(r'collections', CollectionViewSet)
                items = NestedSimpleRouter(collections, r'collections', lookup='collection')
                items.register('addons', ItemViewSet)
                unknown = NestedSimpleRouter(accounts, PREFIX)
                unknown.register('lost', LostViewSet)
                accounts_v5 = [
                    re_path(r'', include(accounts.urls)),
                    re_path(r'', include(collections.urls)),
                    re_path(r'', include(items.urls)),
                    re_path(r'', include(unknown.urls)),
                ]
                """,
            }
        )
        self.assertEqual(
            {path for path, _ in routes(ex)},
            {
                '/api/v5/accounts/account',
                '/api/v5/accounts/account/{pk}',
                '/api/v5/accounts/account/{user_pk}/collections',
                '/api/v5/accounts/account/{user_pk}/collections/{pk}',
                '/api/v5/accounts/account/{user_pk}/collections/{collection_pk}/addons',
                '/api/v5/accounts/account/{user_pk}/collections/{collection_pk}/addons/{pk}',
                '/api/v5/ratings/rating',
                '/api/v5/ratings/rating/{pk}',
            },
        )


class PluginMountsTest(unittest.TestCase):
    def test_plugin_app_url_configs(self):
        ex = extract(
            {
                'proj/settings.py': "ROOT_URLCONF = 'proj.urls'\n",
                'proj/urls.py': 'urlpatterns = []\n',
                'apps/courseware_api/apps.py': """
                class CoursewareApiConfig(AppConfig):
                    name = 'apps.courseware_api'
                    plugin_app = {
                        PluginURLs.CONFIG: {
                            ProjectType.LMS: {
                                PluginURLs.NAMESPACE: 'courseware_api',
                                PluginURLs.REGEX: r'^api/courseware/',
                                PluginURLs.RELATIVE_PATH: 'urls',
                            }
                        },
                    }
                """,
                'apps/courseware_api/urls.py': "urlpatterns = [path('course/<str:key>', course_view)]\n",
                'apps/bookmarks/apps.py': """
                class BookmarksConfig(AppConfig):
                    plugin_app = {PluginURLs.CONFIG: {ProjectType.LMS: {PluginURLs.REGEX: '^api/bookmarks/'}}}
                    other = {'key': 'value'}
                """,
                'apps/bookmarks/urls.py': "urlpatterns = [path('v1/bookmarks/', bookmarks_view)]\n",
                'apps/nothing/apps.py': 'class NothingConfig(AppConfig):\n    plugin_app = make_config()\n',
            }
        )
        self.assertEqual(
            routes(ex), {('/api/courseware/course/{key}', ('ANY',)), ('/api/bookmarks/v1/bookmarks', ('ANY',))}
        )


if __name__ == '__main__':
    unittest.main()
