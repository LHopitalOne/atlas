"""NestRoutes: the routes of NestJS controllers, `@Controller('cats')` classes and their `@Get(':id')` methods."""

from .....core.http import ANY, Extraction
from ...kit import RouteCollector
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .nestapp import NestApplication


class NestDecorators:
    """The decorators of @nestjs/common that place a route, read only when the file imports them from there (a
    `Get` of another library declares nothing)."""

    LIBRARY = '@nestjs/common'
    CONTROLLER = 'Controller'
    VERSION = 'Version'
    VERBS = {
        'Get': 'GET',
        'Post': 'POST',
        'Put': 'PUT',
        'Patch': 'PATCH',
        'Delete': 'DELETE',
        'Head': 'HEAD',
        'Options': 'OPTIONS',
        'Search': 'SEARCH',
        'All': ANY,
    }
    DECORATOR = 'decorator'

    def __init__(self, module):
        self._module = module

    def named(self, decorator):
        """(the @nestjs/common name a decorator calls, its arguments), or ('', [])."""
        call = next((c for c in decorator.named_children if c.type == 'call_expression'), None)
        fn = JsSyntax.unwrap(call.child_by_field_name('function')) if call is not None else None
        if fn is None or fn.type != 'identifier':
            return '', []
        imported = self._module.imports.get(JsSyntax.text(fn))
        if imported is None or imported[0] != self.LIBRARY:
            return '', []
        return imported[1], JsSyntax.args(call)

    def paths(self, args):
        """The paths a decorator's first argument gives: [''] for none, a string, a const or a list of them; None
        when one of them is not known."""
        if not args:
            return ['']
        first = JsSyntax.unwrap(args[0])
        if first.type == 'object':
            given = JsSyntax.prop(first, 'path')
            return self.paths([given]) if given is not None else ['']
        items = first.named_children if first.type == 'array' else [first]
        found = [self.literal(i) for i in items if i.type != 'comment']
        return None if None in found or not found else found

    def literal(self, node):
        """The string a node holds when it is fully known, else None."""
        value = self._module.values.resolve(node, set())
        return value if value is not None and not UrlText.PLACEHOLDER.search(value) else None

    def version(self, args):
        """The `version` a controller's options object gives ('' for none); None when it is not a known string."""
        first = JsSyntax.unwrap(args[0]) if args else None
        given = JsSyntax.prop(first, 'version') if first is not None and first.type == 'object' else None
        return self.literal(given) if given is not None else ''


class NestRoutes(RouteCollector):
    """Each method of a controller decorated with a verb (`@Get(':id')`) serves the controller's path joined with
    the verb's, behind the application's global prefix and URI version (NestApplication). ':id' becomes {id}. A
    controller or verb whose path is not a known string declares no route. The route is placed at its verb's line,
    with the handler named `Controller.method`."""

    framework = 'nestjs'
    MENTIONS = (NestDecorators.LIBRARY.encode(),)
    CLASSES = frozenset({'class_declaration', 'abstract_class_declaration'})

    def collect(self) -> Extraction:
        app, out = None, Extraction()
        linker = self.workspace.linker()
        for source in self.workspace.sources:
            if source.test or not source.mentions(*self.MENTIONS):
                continue
            module = self.workspace.module(source, linker)
            decorators = NestDecorators(module)
            for cls in JsSyntax.walk(source.root, self.CLASSES):
                controller = self._controller(decorators, cls)
                if controller is not None:
                    app = app if app is not None else NestApplication.read(self.workspace)
                    out.routes += self._routes(decorators, app, source, cls, *controller)
        linker.release()
        return out

    def _controller(self, decorators, cls):
        """(controller paths, version) of a class decorated with @Controller, or None."""
        for decorator in self._class_decorators(cls):
            name, args = decorators.named(decorator)
            if name == NestDecorators.CONTROLLER:
                paths, version = decorators.paths(args), decorators.version(args)
                return (paths, version) if paths is not None and version is not None else None
        return None

    @staticmethod
    def _class_decorators(cls):
        """A class's decorators: its own, or those of the `export` statement in front of it."""
        found = [c for c in cls.children if c.type == NestDecorators.DECORATOR]
        parent = cls.parent
        if parent is not None and parent.type == 'export_statement':
            found += [c for c in parent.children if c.type == NestDecorators.DECORATOR]
        return found

    def _routes(self, decorators, app, source, cls, prefixes, version):
        body = cls.child_by_field_name('body')
        owner = JsSyntax.text(cls.child_by_field_name('name'))
        out, pending = [], []
        for child in body.named_children if body is not None else []:
            if child.type == NestDecorators.DECORATOR:
                pending.append(child)
            elif child.type == 'method_definition':
                handler = f'{owner}.{JsSyntax.text(child.child_by_field_name("name"))}'
                out += self._method(decorators, app, source, pending, handler, prefixes, version)
                pending = []
            else:
                pending = []
        return out

    def _method(self, decorators, app, source, found, handler, prefixes, version):
        """The routes the decorators of one method declare."""
        named = [(decorators.named(d), d) for d in found]
        version = self._version(decorators, named, version)
        if version is None:
            return []  # a @Version that is not a known string
        version = version or app.default_version
        out = []
        for (name, args), decorator in named:
            method = NestDecorators.VERBS.get(name)
            paths = decorators.paths(args) if method is not None else None
            for prefix in prefixes if paths is not None else ():
                for path in paths:
                    full = app.path(f'{prefix.strip("/")}/{path.strip("/")}', version, method)
                    out.append(self.route(source, JsSyntax.line(decorator), full, {method}, handler))
        return out

    @staticmethod
    def _version(decorators, named, version):
        """The version a method's @Version gives, else its controller's."""
        for (name, args), _ in named:
            if name == NestDecorators.VERSION:
                return decorators.literal(args[0]) if args else None
        return version
