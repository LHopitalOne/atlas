"""NextRoutes: the API routes of a Next.js app, named by their files (`pages/api/` and `app/**/route.ts`)."""

from .....core.http import ANY, Extraction
from ...kit import RouteCollector
from ..bindings.exports import ModuleExports
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from .nextpaths import NextPath


class MethodChecks:
    """The HTTP methods a pages-router handler tells apart: `req.method === 'POST'`, `req.method !== 'GET'`,
    `switch (req.method) { case 'PUT': ... }`, `['GET', 'HEAD'].includes(req.method)`."""

    VERBS = frozenset({'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'})
    COMPARISONS = frozenset({'===', '==', '!==', '!='})
    PROPERTY = 'method'
    INCLUDES = 'includes'
    NODES = frozenset({'binary_expression', 'switch_statement', 'call_expression'})

    @classmethod
    def found(cls, root) -> list:
        """[(method, node that names it)] in source order."""
        out = []
        for node in JsSyntax.walk(root, cls.NODES):
            if node.type == 'binary_expression':
                out += cls._comparison(node)
            elif node.type == 'switch_statement':
                out += cls._switch(node)
            else:
                out += cls._includes(node)
        return [(m, n) for m, n in out if m in cls.VERBS]

    @classmethod
    def _is_method(cls, node):
        node = JsSyntax.unwrap(node)
        return node is not None and node.type == 'member_expression' and cls._property(node) == cls.PROPERTY

    @staticmethod
    def _property(member):
        return JsSyntax.text(member.child_by_field_name('property'))

    @staticmethod
    def _verb(node):
        node = JsSyntax.unwrap(node)
        return (JsSyntax.string(node) or '').upper() if node is not None and node.type == 'string' else ''

    @classmethod
    def _comparison(cls, node):
        if JsSyntax.text(node.child_by_field_name('operator')) not in cls.COMPARISONS:
            return []
        left, right = node.child_by_field_name('left'), node.child_by_field_name('right')
        if cls._is_method(left):
            return [(cls._verb(right), node)]
        return [(cls._verb(left), node)] if cls._is_method(right) else []

    @classmethod
    def _switch(cls, node):
        if not cls._is_method(node.child_by_field_name('value')):
            return []
        body = node.child_by_field_name('body')
        cases = [c for c in body.named_children if c.type == 'switch_case'] if body is not None else []
        return [(cls._verb(c.child_by_field_name('value')), c) for c in cases]

    @classmethod
    def _includes(cls, node):
        fn, args = JsSyntax.unwrap(node.child_by_field_name('function')), JsSyntax.args(node)
        if fn is None or fn.type != 'member_expression' or cls._property(fn) != cls.INCLUDES:
            return []
        array = JsSyntax.unwrap(fn.child_by_field_name('object'))
        if not args or not cls._is_method(args[0]) or array is None or array.type != 'array':
            return []
        return [(cls._verb(item), item) for item in array.named_children]


class NextRoutes(RouteCollector):
    """A file under `pages/api/` serves its path with the handler it exports by default, for the methods the
    handler checks `req.method` against (ANY when it checks none). An app-router `route` file serves its folder's
    path with one handler per exported HTTP method (`export async function GET(request)`). Dynamic segments become
    parameters: `[id]` -> {id}, `[...slug]` and `[[...slug]]` -> {*slug}."""

    framework = 'nextjs'

    def collect(self) -> Extraction:
        out = Extraction()
        for source in self.workspace.sources:
            if source.test:
                continue
            pages, app = NextPath.pages_api(source.path), NextPath.app_route(source.path)
            if pages is None and app is None:
                continue
            exports = ModuleExports(source)
            out.routes += self._pages(source, pages, exports) if pages is not None else self._app(source, app, exports)
            source.release()
        return out

    def _pages(self, source, path, exports):
        handler = exports.value(ModuleExports.DEFAULT)
        if handler is None:
            return []  # Next.js serves a file's default export: without one it is not a route
        checks = MethodChecks.found(source.root)
        if not checks:
            return [self.route(source, JsSyntax.line(handler), path, {ANY}, self._name(handler))]
        first = {}
        for method, node in checks:
            first.setdefault(method, node)
        return [self.route(source, JsSyntax.line(n), path, {m}, Functions.enclosing(n)[0]) for m, n in first.items()]

    def _app(self, source, path, exports):
        verbs = sorted((name, node) for name, node in exports.names().items() if name in MethodChecks.VERBS)
        return [self.route(source, JsSyntax.line(node), path, {verb}, self._name(node)) for verb, node in verbs]

    @staticmethod
    def _name(node):
        """The name of an exported handler: a function's own name, a name, or the last name a wrapper is given."""
        node = JsSyntax.unwrap(node)
        if node.type == 'identifier':
            return JsSyntax.text(node)
        if node.type == 'call_expression':
            names = [a for a in JsSyntax.args(node) if a.type == 'identifier']
            return JsSyntax.text(names[-1]) if names else ''
        name = node.child_by_field_name('name')
        return JsSyntax.text(name) if name is not None else ''
