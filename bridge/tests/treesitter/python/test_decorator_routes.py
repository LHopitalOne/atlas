import textwrap
import unittest
from unittest import mock

from atlas_bridge.adapters.treesitter.python import PythonExtractor
from atlas_bridge.adapters.treesitter.python.routes import Registrations
from atlas_bridge.core.http import ANY

from .support import extract, requests_, routes, workspace


class DecoratorRouteTest(unittest.TestCase):
    def test_flask_app_and_blueprints(self):
        ex = extract(
            {
                'app/views.py': """
                from flask import Flask, Blueprint
                application = Flask(__name__)
                bp = Blueprint('bp', __name__, url_prefix='/bp')

                @application.route('/rpc/<name>/<version>', methods=['POST'])
                def rpc(name, version):
                    pass

                @application.route('/<dataset:dataset>/snql', methods=['GET', 'POST'])
                @other.decorator
                def snql(dataset):
                    pass

                @application.route('/health')
                def health():
                    pass

                @bp.get('/items/<int:item_id>')
                def item(item_id):
                    pass

                @application.route('/dyn', methods=METHODS)
                def dyn():
                    pass

                @application.route('not a path')
                @application.cache.get('key')
                def nope():
                    pass

                @application.route
                def bare():
                    pass

                @decorator
                class C:
                    pass

                application.add_url_rule('/rule/<path:rest>', 'rule', view_func=rule_view, methods=['PUT'])
                application.add_url_rule(rule=None)
                """,
                'app/main.py': """
                from app.views import bp
                from app import views
                app.register_blueprint(bp, url_prefix='/v2')
                app.register_blueprint(views.unknown, url_prefix='/x')
                app.register_blueprint(bp)
                """,
            }
        )
        self.assertEqual(
            routes(ex),
            {
                ('/rpc/{name}/{version}', ('POST',)),
                ('/{dataset}/snql', ('GET', 'POST')),
                ('/health', ('GET',)),
                ('/v2/items/{item_id}', ('GET',)),
                ('/dyn', (ANY,)),
                ('/rule/{*rest}', ('PUT',)),
            },
        )
        r = next(r for r in ex.routes if str(r.path) == '/rpc/{name}/{version}')
        self.assertEqual((r.file, r.line, r.handler, r.framework), ('app/views.py', 6, 'rpc', 'flask'))
        self.assertEqual(next(r for r in ex.routes if str(r.path) == '/rule/{*rest}').handler, 'rule_view')

    def test_fastapi_routers(self):
        ex = extract(
            {
                'api/routes.py': """
                from fastapi import APIRouter, FastAPI
                router = APIRouter(prefix='/items')
                app = FastAPI()

                @router.get('/{item_id}')
                async def read(item_id):
                    pass

                @router.api_route('/files/{p:path}', methods=['GET', 'POST'])
                def files(p):
                    pass

                @app.post('/root')
                def root():
                    pass

                app.include_router(router, prefix='/api')
                """
            }
        )
        self.assertEqual(
            routes(ex),
            {('/api/items/{item_id}', ('GET',)), ('/api/items/files/{*p}', ('GET', 'POST')), ('/root', ('POST',))},
        )
        self.assertEqual({r.framework for r in ex.routes}, {'fastapi'})

    def test_empty_paths_name_the_prefix(self):
        ex = extract(
            {
                'api/items.py': """
                from fastapi import APIRouter
                router = APIRouter(prefix='/items')

                @router.get('')
                def list_items():
                    pass

                @router.post('/')
                def create():
                    pass
                """,
                'web/things.py': """
                from flask import Blueprint
                bp = Blueprint('things', __name__, url_prefix='/things')
                other = make()

                @bp.route('', methods=['GET'])
                def things():
                    pass

                @other.get('')
                def not_a_route():
                    pass
                """,
            }
        )
        self.assertEqual(routes(ex), {('/items', ('GET',)), ('/items', ('POST',)), ('/things', ('GET',))})

    def test_methods_lists(self):
        ex = extract(
            {
                'app.py': """
                from flask import Flask
                app = Flask(__name__)
                M = ['GET', 'post']

                @app.route('/named', methods=M)
                def named():
                    pass

                @app.route('/mixed', methods=['GET', verb])
                def mixed():
                    pass

                @app.route('/call', methods=allowed())
                def call():
                    pass
                """
            }
        )
        self.assertEqual(routes(ex), {('/named', ('GET', 'POST')), ('/mixed', (ANY,)), ('/call', (ANY,))})

    def test_bare_add_url_rule_has_no_prefix(self):
        ex = extract({'app.py': "add_url_rule('/bare', 'bare', view_func=bare)\n"})
        self.assertEqual(routes(ex), {('/bare', ('GET',))})
        self.assertEqual(ex.routes[0].framework, 'flask')


class PrefixedTemplateTest(unittest.TestCase):
    FILES = {
        'app.py': """
        from flask import Blueprint
        bp = Blueprint('bp', __name__)
        app.register_blueprint(bp, url_prefix='/v1')

        @bp.route('/a')
        def a():
            pass

        bp.add_url_rule('/b', 'b', view_func=b)
        """
    }

    def test_registrations_are_read_once_and_collect_is_repeatable(self):
        ws = workspace({k: textwrap.dedent(v) for k, v in self.FILES.items()})
        reads = []
        calls = ws.calls

        def counting(names):
            reads.append(frozenset(names))
            return calls(names)

        with mock.patch.object(ws, 'calls', counting):
            collectors = PythonExtractor().collectors(ws)
        self.assertEqual(reads.count(Registrations.NAMES), 1)
        decorators, rules = collectors[0], collectors[1]
        self.assertEqual([str(r.path) for r in decorators.collect().routes], ['/v1/a'])
        self.assertEqual([str(r.path) for r in decorators.collect().routes], ['/v1/a'])  # no duplicates
        self.assertEqual([str(r.path) for r in rules.collect().routes], ['/v1/b'])


class DecoratorsAreNotRequestsTest(unittest.TestCase):
    def test_a_route_decorator_is_not_a_request(self):
        ex = extract(
            {
                'svc/api.py': """
                from aiohttp import web
                routes = web.RouteTableDef()

                @routes.get('/healthz')
                async def health(request):
                    return web.json_response({'status': 'ok'})
                """,
            }
        )
        self.assertEqual(requests_(ex), set())


class NestedRoutersTest(unittest.TestCase):
    def test_a_router_included_in_a_router_is_under_its_whole_prefix(self):
        ex = extract(
            {
                'app/routes/notes/items.py': """
                from fastapi import APIRouter
                router = APIRouter()

                @router.get('/draft')
                async def draft(): ...
                """,
                'app/routes/notes/__init__.py': """
                from fastapi import APIRouter
                from . import items
                router = APIRouter(prefix='/api/notes')
                router.include_router(items.router)
                """,
                'app/routes/admin.py': """
                from fastapi import APIRouter
                from app.routes.notes import router as notes_router
                router = APIRouter(prefix='/admin')
                router.include_router(notes_router, prefix='/v2')

                @router.get('/stats')
                async def stats(): ...
                """,
                'app/main.py': """
                from fastapi import FastAPI
                from app.routes.admin import router as admin_router
                app = FastAPI()
                app.include_router(admin_router, prefix='/x')
                """,
            }
        )
        self.assertEqual(routes(ex), {('/x/admin/v2/api/notes/draft', ('GET',)), ('/x/admin/stats', ('GET',))})
