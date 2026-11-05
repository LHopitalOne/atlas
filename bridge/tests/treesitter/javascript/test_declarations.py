import unittest

from atlas_bridge.adapters.treesitter.javascript.declarations.mounts import MountSyntax
from atlas_bridge.adapters.treesitter.javascript.declarations.records import Declaration, Mount, RouteDeclaration
from atlas_bridge.adapters.treesitter.javascript.declarations.routes import (
    ChainedRouteSyntax,
    FastifyRouteSyntax,
    RouteSyntax,
    VerbRoutes,
    VerbRouteSyntax,
)
from atlas_bridge.adapters.treesitter.javascript.declarations.syntax import DeclarationSyntax
from atlas_bridge.adapters.treesitter.javascript.routes.files import FileRoutes
from atlas_bridge.adapters.treesitter.javascript.syntax.site import CallSite
from atlas_bridge.core.http import ANY

from .support import Repository

SOURCE = (
    'const app = express();\n'
    "app.use('/api', router);\n"
    'app.use(cors());\n'
    "app.get('/orders/:id', show);\n"
    "app.route('/book').get(getBook);\n"
    "fastify.route({method: 'POST', url: '/f', handler: h});\n"
    "api.get('/request');\n"
    "get('/plain', h);\n"
)


class RouteSyntaxesTest(unittest.TestCase):
    def setUp(self):
        ws = Repository.workspace([('src/a.js', SOURCE)])
        self.module = ws.module(ws.sources[0])
        self.found = [(s.name, self.module.route_syntax.declaration(s)) for s in self.module.sites()]

    def test_each_name_is_read_by_its_syntax(self):
        kinds = [(name, type(d).__name__ if d else None) for name, d in self.found]
        self.assertEqual(
            kinds,
            [
                ('use', 'Mount'),
                ('use', None),  # middleware, no prefix
                ('get', 'RouteDeclaration'),
                ('route', None),  # app.route('/book') alone declares nothing...
                ('get', 'RouteDeclaration'),  # ...its chained `.get` declares the route
                ('route', 'RouteDeclaration'),
                ('get', None),  # a request
                ('get', None),  # not a member call
            ],
        )
        self.assertIs(self.module.route_syntax, self.module.route_syntax)

    def test_declarations_add_themselves_to_their_file(self):
        found = FileRoutes(self.module)
        for _, declaration in self.found:
            if declaration is not None:
                self.assertIsInstance(declaration, Declaration)
                declaration.add_to(found)
        self.assertEqual([m.prefix for m in found.mounts], ['/api'])
        self.assertEqual(
            [(r.receiver, r.path, r.methods, r.handler) for r in found.routes],
            [
                ('app', '/orders/:id', frozenset({'GET'}), 'show'),
                ('app', '/book', frozenset({'GET'}), 'getBook'),
                ('fastify', '/f', frozenset({'POST'}), 'h'),
            ],
        )
        self.assertTrue(found)
        self.assertFalse(FileRoutes(self.module))

    def test_the_syntaxes_share_one_base(self):
        for syntax in (ChainedRouteSyntax, VerbRouteSyntax, VerbRoutes, FastifyRouteSyntax):
            self.assertTrue(issubclass(syntax, RouteSyntax))
        self.assertTrue(issubclass(MountSyntax, DeclarationSyntax))
        self.assertTrue(issubclass(RouteSyntax, DeclarationSyntax))
        self.assertTrue(issubclass(RouteDeclaration, Declaration) and issubclass(Mount, Declaration))


class MethodsTest(unittest.TestCase):
    def test_one_rule_names_the_method_of_a_verb(self):
        self.assertEqual(CallSite.method_of('get'), 'GET')
        self.assertEqual(CallSite.method_of('del'), 'DELETE')
        self.assertEqual(CallSite.method_of('delete'), 'DELETE')
        self.assertEqual(RouteSyntax.methods('del'), frozenset({'DELETE'}))
        self.assertEqual(RouteSyntax.methods('all'), frozenset({ANY}))
        self.assertEqual(RouteSyntax.methods(None), frozenset({ANY}))

    def test_del_is_a_delete_request_and_route(self):
        self.assertIn(('DELETE', '/x'), Repository.calls("api.del('/x');"))
        self.assertIn(('DELETE', '/y'), Repository.routes({'a.js': "router.del('/y', h);"}))


if __name__ == '__main__':
    unittest.main()
