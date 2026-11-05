import unittest

from atlas_bridge.adapters.treesitter.python.routes.django import (
    Composition,
    UrlComposer,
    UrlEntries,
    UrlLists,
    ViewMethods,
)
from atlas_bridge.adapters.treesitter.python.values import PythonValueResolver
from atlas_bridge.core.http import ANY

from .support import extract, workspace

DJANGO = {
    'proj/settings.py': """
    ROOT_URLCONF = 'proj.urls'
    """,
    'proj/tests/settings.py': """
    ROOT_URLCONF = 'proj.test_urls'
    """,
    'proj/urls.py': """
    from django.urls import include, path, re_path
    from proj.api.urls import urlpatterns as api_patterns

    urlpatterns = [
        re_path(r'^api/0/', include('proj.api.urls')),
        path('v2/', include(api_patterns)),
        re_path(r'^ext/', include([re_path(r'^gh/', include('proj.ext.urls'))])),
        re_path(r'^loop/', include('proj.urls')),
        re_path(r'^gone/', include('nowhere.urls')),
        re_path(r'^none/', include()),
        url(r'^old/(?P<id>\\d+)/$', views.old, name='old'),
    ]
    urlpatterns += [path('extra/<int:pk>/', views.extra)]
    urlpatterns.append(path('appended/', views.appended))
    urlpatterns.extend([path('extended/', views.extended)])
    urlpatterns.insert(0, path('inserted/', views.inserted))
    if DEBUG:
        urlpatterns += patterns('', url(r'^debug/$', views.debug))
    """,
    'proj/api/urls.py': """
    from django.urls import include, re_path
    from proj.api.endpoints import RelayHealthCheck, RelayRegister
    from proj.api import shared
    from .more import MORE_URLS

    def make_urls(name_prefix, legacy=False):
        details = [re_path(r'^(?P<issue_id>[^/]+)/$', GroupDetails.as_view(), name=f'{name_prefix}-details')]
        return details + [re_path(r'^(?P<issue_id>[^/]+)/notes/$', Notes.as_view(), name=f'{name_prefix}-notes')]

    RELAY_URLS = [
        re_path(r'^register/challenge/$', RelayRegister.as_view(), name='relay-register'),
        re_path(r'^live/$', RelayHealthCheck.as_view(), name='relays-healthcheck'),
    ]
    PROJECT_URLS = (
        re_path(
            r'^(?P<organization_id_or_slug>[^/]+)/(?P<project_id_or_slug>[^/]+)/files/dsyms/$',
            csrf_exempt(DebugFilesEndpoint.as_view()),
            name='dsym-files',
        ),
    )
    urlpatterns = [
        re_path(r'^relays/', include(RELAY_URLS)),
        re_path(r'^projects/', include((PROJECT_URLS, 'projects'), namespace='p')),
        re_path(r'^(?:issues|groups)/', include(make_urls('api-0', legacy=True))),
        re_path(r'^shared/', include(shared.SHARED_URLS)),
        re_path(r'^more/', include(MORE_URLS + [re_path(r'^tail/$', views.tail)])),
        re_path(r'^var/', include(list(VARIANTS))),
        re_path(PATTERN, views.dynamic),
        *shared.SPLAT_URLS,
    ]
    VARIANTS = [re_path(r'^v/$', views.v)]
    PATTERN = r'^dyn/$'
    """,
    'proj/api/shared.py': """
    SHARED_URLS = [re_path(r'^one/$', views.one)]
    SPLAT_URLS = [re_path(r'^splat/$', views.splat)]
    """,
    'proj/api/more.py': """
    MORE_URLS = [re_path(r'^m/$', views.m)]
    """,
    'proj/api/endpoints/__init__.py': """
    from .relay import RelayHealthCheck, RelayRegister
    """,
    'proj/api/endpoints/relay.py': """
    class Endpoint:
        def options(self, request):
            pass

    class RelayHealthCheck(Endpoint):
        def get(self, request):
            pass

    class RelayRegister(Endpoint):
        @decorated
        def post(self, request):
            pass

        x = 1
    """,
    'proj/api/endpoints/debug.py': """
    class Base:
        def get(self, request):
            pass

        def delete(self, request):
            pass

    class DebugFilesEndpoint(Base):
        pass

    class Notes(Missing, mod.Other):
        pass
    """,
    'proj/ext/urls.py': """
    urlpatterns = [re_path(r'^webhook/$', Webhook.as_view())]
    """,
}


class DjangoRouteTest(unittest.TestCase):
    def test_includes_compose_from_root_urlconf(self):
        ex = extract(DJANGO)
        got = {str(r.path): r for r in ex.routes}
        live = got['/api/0/relays/live']
        self.assertEqual(
            (live.methods, live.handler, live.name), (frozenset({'GET'}), 'RelayHealthCheck', 'relays-healthcheck')
        )
        self.assertEqual((live.file, live.framework), ('proj/api/urls.py', 'django'))
        self.assertEqual(got['/api/0/relays/register/challenge'].methods, frozenset({'POST'}))
        dsyms = got['/api/0/projects/{organization_id_or_slug}/{project_id_or_slug}/files/dsyms']
        self.assertEqual((dsyms.name, dsyms.methods), ('dsym-files', frozenset({'GET', 'DELETE'})))
        self.assertEqual(got['/api/0/issues/{issue_id}'].name, 'api-0-details')
        self.assertEqual(got['/api/0/groups/{issue_id}/notes'].methods, frozenset({ANY}))
        for p in (
            '/v2/relays/live',
            '/ext/gh/webhook',
            '/api/0/shared/one',
            '/api/0/splat',
            '/api/0/more/m',
            '/api/0/more/tail',
            '/api/0/var/v',
            '/api/0/dyn',
            '/old/{id}',
            '/extra/{pk}',
            '/appended',
            '/extended',
            '/inserted',
            '/debug',
            '/loop/api/0/relays/live',
        ):
            self.assertIn(p, got)
        self.assertEqual(got['/extra/{pk}'].methods, frozenset({ANY}))
        self.assertEqual(got['/old/{id}'].handler, 'views.old')
        self.assertFalse(any(p.startswith('/gone') or p.startswith('/loop/loop') for p in got))

    def test_without_root_urlconf_every_unincluded_module_is_a_root(self):
        files = {k: v for k, v in DJANGO.items() if 'settings' not in k}
        files['other/urls.py'] = "urlpatterns = [re_path(r'^solo/$', views.solo)]\n"
        got = {str(r.path) for r in extract(files).routes}
        self.assertIn('/solo', got)
        self.assertIn('/api/0/relays/live', got)
        self.assertNotIn('/relays/live', got)
        self.assertNotIn('/webhook', got)

    def test_reassignment_that_reads_itself_keeps_earlier_entries(self):
        ex = extract(
            {
                'a/urls.py': """
                urlpatterns = [path('v/', V)]
                urlpatterns = urlpatterns + [path('w/', W)]
                urlpatterns = [*urlpatterns, path('x/', X)]
                """,
                'b/urls.py': """
                urlpatterns = [path('old/', Old)]
                urlpatterns = [path('new/', New)]
                """,
            }
        )
        self.assertEqual({str(r.path) for r in ex.routes}, {'/v', '/w', '/x', '/new'})


class ComposerTest(unittest.TestCase):
    def test_composer_needs_only_a_route_factory_and_the_name_lookup(self):
        ws = workspace(
            {
                'proj/urls.py': "urlpatterns = [path('api/', include('proj.api')), path('top/', top)]\n",
                'proj/api.py': "urlpatterns = [path('ping/', ping, name='ping')]\n",
            }
        )
        values = PythonValueResolver(ws)
        made = []

        def route(source, line, path, methods, handler, name):
            made.append((source.path, path, handler, name))
            return path

        composer = UrlComposer(route, ws.names, values, UrlEntries(ws, values, UrlLists()), ViewMethods(ws))
        out = composer.compose(ws.source('proj/urls.py'), 'urlpatterns')
        self.assertEqual(out.routes, ['/api/ping/', '/top/'])
        self.assertEqual(out.included, frozenset({'proj/api.py'}))
        self.assertEqual(made[0], ('proj/api.py', '/api/ping/', 'ping', 'ping'))

    def test_composition_hides_its_state(self):
        out = Composition()
        out.add_route('r')
        out.include('a.py')
        out.routes.append('not kept')
        self.assertEqual(out.routes, ['r'])
        self.assertEqual(out.included, frozenset({'a.py'}))
        with self.assertRaises(AttributeError):
            out.included.add('b.py')
