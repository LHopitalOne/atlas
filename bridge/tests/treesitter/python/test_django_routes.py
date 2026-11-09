import unittest

from atlas_bridge.adapters.treesitter.python.routes.django import (
    Composition,
    DrfRouters,
    LoopValues,
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


HELPERS = {
    'proj/settings.py': """
    ROOT_URLCONF = 'proj.urls'
    if RUNNING_EVENTS:
        ROOT_URLCONF = 'proj.event_urls'
    """,
    'proj/rest.py': """
    from django.urls import path

    def rest_path(route, **handlers):
        return path(route, dispatch, handlers)

    def api_path(route, **handlers):
        return rest_path(f'api/{route}', **handlers)

    def make_urls(prefix):
        return [path(f'{prefix}/list/', listing)]
    """,
    'proj/urls.py': """
    from django.urls import include, path
    from proj.rest import api_path, make_urls, rest_path

    v1_patterns = [
        rest_path('users', GET=list_users, POST=(add_user, {'flag'})),
        rest_path('users/<int:user_id>', PATCH=update_user, DELETE=delete_user),
        rest_path(ROUTE, GET=dynamic),
        api_path('nested', PUT=nested_view),
        path('plain/', plain_view),
    ]
    pages: list[object] = [path('home/', home)]
    urls: list[object] = list(pages)
    urls += [path('v1/', include(v1_patterns)), path('json/', include(v1_patterns))]
    urls.extend([path('built/', include(make_urls('b')))])
    if DEBUG:
        urls += [path('debug/', debug_view)]
    urls += [path('const/', include(CONST_MODULE)), path('fmt/', include(f'{PACKAGE}.urls'))]
    for app in ['proj.billing', 'proj.missing']:
        urls += [path('', include(f'{app}.urls'))]
    for app in settings.EXTRA_APPS:
        urls += [path('extra/', include(f'{app}.urls'))]
    for old in REDIRECTS:
        urls += [path(old, redirect_view)]
    for name in ['a', 'b']:
        urls += [path(name_route, redirect_view)]
    urlpatterns = i18n_patterns(*pages) + urls
    CONST_MODULE = 'proj.const_urls'
    PACKAGE = 'proj.fmt'
    """,
    'proj/event_urls.py': """
    from proj.rest import rest_path
    urlpatterns = [rest_path('events', GET=get_events, DELETE=cleanup)]
    """,
    'proj/const_urls.py': "urlpatterns = [path('c/', c_view)]\n",
    'proj/fmt/urls.py': "urlpatterns = [path('f/', f_view)]\n",
    'proj/billing/urls.py': """
    from proj.rest import rest_path as helper
    urlpatterns = [helper('billing/plan', PATCH=update_plan)]
    """,
    'proj/plugin/urls.py': "urlpatterns = [path('p/', p_view)]\n",
    'proj/conf/settings.py': """
    from .defaults import *
    from .dev import *
    """,
    'proj/conf/defaults.py': "EXTRA_APPS = ['nowhere']\n",
    'proj/conf/dev.py': "EXTRA_APPS = ['proj.plugin']\n",
}


class RouteHelperTest(unittest.TestCase):
    def setUp(self):
        self.routes = extract(HELPERS).routes

    def found(self, path):
        return {(sorted(r.methods)[0], r.handler, r.file, r.line) for r in self.routes if str(r.path) == path}

    def test_helper_calls_declare_one_route_per_method_keyword(self):
        self.assertEqual(
            self.found('/v1/users'),
            {('GET', 'list_users', 'proj/urls.py', 6), ('POST', 'add_user', 'proj/urls.py', 6)},
        )
        self.assertEqual(
            self.found('/json/users/{user_id}'),
            {('PATCH', 'update_user', 'proj/urls.py', 7), ('DELETE', 'delete_user', 'proj/urls.py', 7)},
        )
        self.assertEqual(self.found('/v1/api/nested'), {('PUT', 'nested_view', 'proj/urls.py', 9)})
        self.assertEqual(self.found('/v1/plain'), {(ANY, 'plain_view', 'proj/urls.py', 10)})
        self.assertEqual(self.found('/v1/{param}'), {('GET', 'dynamic', 'proj/urls.py', 8)})

    def test_every_root_urlconf_assignment_is_a_root(self):
        self.assertEqual(
            self.found('/events'),
            {('GET', 'get_events', 'proj/event_urls.py', 3), ('DELETE', 'cleanup', 'proj/event_urls.py', 3)},
        )
        self.assertEqual(self.found('/billing/plan'), {('PATCH', 'update_plan', 'proj/billing/urls.py', 3)})

    def test_composed_lists_and_included_modules(self):
        got = {str(r.path) for r in self.routes}
        for p in ('/home', '/built/b/list', '/debug', '/const/c', '/fmt/f', '/billing/plan', '/extra/p'):
            self.assertIn(p, got)
        self.assertFalse(any(p.startswith(('/{', '/extra/{')) for p in got), got)
        self.assertNotIn('/', got)

    def test_loop_values_need_literal_strings(self):
        ws = workspace({'m.py': "APPS = ('a', f'{x}', 3)\nfor app in APPS:\n    pass\nfor a, b in APPS:\n    pass\n"})
        source = ws.source('m.py')
        loops = list(source.root.named_children)[1:]
        found = LoopValues(ws, PythonValueResolver(ws))
        self.assertEqual(found.values(source, loops[0]), [{'app': 'a'}])
        self.assertEqual(found.values(source, loops[1]), [])


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

        routers = DrfRouters(ws, values)
        entries = UrlEntries(ws, values, UrlLists(), routers)
        composer = UrlComposer(route, ws.names, values, entries, ViewMethods(ws), routers)
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
