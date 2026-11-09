"""How a NestJS application places its controllers: `app.setGlobalPrefix('api', { exclude })` and
`app.enableVersioning({ type: VersioningType.URI })`, read from the bootstrap code wherever it is."""

from .....core.http import ANY
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .paths import ExpressPath


class NestApplication:
    """The global prefix every route is served under (unless excluded), and the URI versioning of routes. Each is read
    from the calls the bootstrap makes on the application; a repository whose calls disagree (two applications with
    different prefixes) gets none, since which prefix a controller is served under cannot be told."""

    PREFIX = 'setGlobalPrefix'
    VERSIONING = 'enableVersioning'
    CALLS = (PREFIX.encode(), VERSIONING.encode())
    EXCLUDE = 'exclude'
    URI_TYPE = 'URI'  # VersioningType.URI: the version is a path segment
    VERSION_PREFIX = 'v'  # the default segment prefix of URI versioning ('/v1/...')
    ALL_METHODS = 'ALL'  # RequestMethod.ALL, and an exclude entry that is a bare path: every method

    def __init__(self, prefix='', excluded=(), versioning=None):
        self._prefix = prefix.strip('/')
        self._excluded = tuple(excluded)
        self._versioning = versioning  # (segment prefix, default version) when URI versioning is on, else None

    @classmethod
    def read(cls, workspace) -> 'NestApplication':
        """The settings of the application(s) bootstrapped in the workspace's files."""
        prefixes, excluded, versionings = set(), [], set()
        linker = workspace.linker()
        for source in workspace.sources:
            if source.test or not source.mentions(*cls.CALLS):
                continue
            module = workspace.module(source, linker)
            for call in JsSyntax.walk(source.root, {'call_expression'}):
                name = cls._method(call)
                if name == cls.PREFIX:
                    prefixes.add(cls._prefix_of(module, call))
                    excluded += cls._excluded_of(module, call)
                elif name == cls.VERSIONING:
                    versionings.add(cls._versioning_of(module, call))
        linker.release()
        prefix = prefixes.pop() if len(prefixes) == 1 else None
        versioning = versionings.pop() if len(versionings) == 1 else None
        return cls(prefix or '', excluded if prefix else (), versioning)

    @property
    def versioned(self) -> bool:
        """The application serves routes under a version segment."""
        return self._versioning is not None

    @property
    def default_version(self) -> str:
        return self._versioning[1] if self._versioning is not None else ''

    def path(self, route_path: str, version: str = '', method: str = '') -> str:
        """The path a controller route is served at: behind the global prefix (unless excluded for its method) and
        the version."""
        route = ExpressPath.canonical(route_path)
        parts = [self._prefix] if self._prefix and not self._is_excluded(route, method) else []
        if self._versioning is not None and version:
            parts.append(self._versioning[0] + version)
        parts.append(route.strip('/'))
        return '/' + '/'.join(p for p in parts if p)

    def _is_excluded(self, route, method):
        """An exclude entry matches the route: its method (or every method) and its path, where a parameter
        segment matches any one segment and a trailing wildcard ('(.*)', '*splat', '{*splat}') the rest."""
        segments = [s for s in route.split('/') if s]
        for path, excluded_method in self._excluded:
            if excluded_method not in (self.ALL_METHODS, method) and method != ANY:
                continue
            if self._matches([s for s in path.split('/') if s], segments):
                return True
        return False

    @staticmethod
    def _matches(pattern, segments):
        for i, part in enumerate(pattern):
            if part.startswith('{*'):
                return True
            if i >= len(segments) or (part != segments[i] and not part.startswith('{')):
                return False
        return len(pattern) == len(segments)

    @staticmethod
    def _method(call):
        fn = JsSyntax.unwrap(call.child_by_field_name('function'))
        if fn is None or fn.type != 'member_expression':
            return ''
        return JsSyntax.text(fn.child_by_field_name('property'))

    @classmethod
    def _prefix_of(cls, module, call):
        """The prefix a call sets, or None when it is not a literal."""
        args = JsSyntax.args(call)
        value = cls._literal(module, args[0]) if args else None
        return value.strip('/') if value is not None else None

    @classmethod
    def _excluded_of(cls, module, call):
        """The routes `{ exclude: [...] }` keeps out of the prefix, as (canonical path, method): each a path string
        (every method) or a `{ path, method: RequestMethod.GET }` object, in a list literal or a const one."""
        args = JsSyntax.args(call)
        given = JsSyntax.prop(args[1], cls.EXCLUDE) if len(args) > 1 else None
        found = module.objects.locate(given) if given is not None else None
        items = JsSyntax.unwrap(found.node) if found is not None else None
        if items is None or items.type != 'array':
            return []
        out = []
        for item in items.named_children:
            is_object = JsSyntax.unwrap(item).type == 'object'
            path = JsSyntax.prop(item, 'path') if is_object else item
            value = cls._literal(found.module, path) if path is not None else None
            if value is not None:
                out.append((ExpressPath.canonical(value), cls._excluded_method(item if is_object else None)))
        return out

    @classmethod
    def _excluded_method(cls, item):
        """The method an exclude entry names (`RequestMethod.GET` -> 'GET'); every method when it names none."""
        given = JsSyntax.prop(item, 'method') if item is not None else None
        name = JsSyntax.last_name(given).upper() if given is not None else ''
        return name if name.isalpha() else cls.ALL_METHODS

    @classmethod
    def _versioning_of(cls, module, call):
        """(segment prefix, default version) of URI versioning, or None for another type or an unread one."""
        args = JsSyntax.args(call)
        options = JsSyntax.unwrap(args[0]) if args else None
        kind = JsSyntax.prop(options, 'type') if options is not None else None
        if kind is None or JsSyntax.last_name(kind) != cls.URI_TYPE:
            return None
        prefix = JsSyntax.prop(options, 'prefix')
        prefix = cls._literal(module, prefix) if prefix is not None else cls.VERSION_PREFIX
        default = JsSyntax.prop(options, 'defaultVersion')
        default = cls._literal(module, default) if default is not None else ''
        return None if prefix is None else (prefix, default or '')

    @staticmethod
    def _literal(module, node):
        """The string a node is bound to when it is fully known; None otherwise."""
        value = module.values.resolve(node, set())
        return value if value is not None and not UrlText.PLACEHOLDER.search(value) else None
