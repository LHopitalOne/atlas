"""GraphQL schemas written code-first with Strawberry: the fields of the root types are routes '/<fieldName>'."""

import dataclasses

from .....core.http import ANY, Extraction, Protocol
from ...kit import RouteCollector
from ..syntax import PythonSyntax
from .qualified import QualifiedNames


class StrawberryFields(RouteCollector):
    """The root types of a Strawberry schema: the `@strawberry.type` classes handed to `strawberry.Schema(query=...,
    mutation=..., subscription=...)`, and those named Query, Mutation or Subscription. Each field (a method decorated
    `@strawberry.field` / `mutation` / `subscription`, or an annotated attribute) is a route named as clients write it:
    its `name=`, else the Python name in camelCase, Strawberry's default (`auto_camel_case=False` turns that off)."""

    LIBRARY = 'strawberry'
    TYPE = 'type'  # strawberry.type, strawberry.federation.type
    SCHEMA = 'Schema'
    ROOTS = frozenset({'query', 'mutation', 'subscription'})  # Schema's keywords, and (capitalised) the root names
    FIELDS = frozenset({'field', 'mutation', 'subscription'})
    HIDDEN = frozenset({'Private', 'ClassVar'})  # annotations of attributes that are not GraphQL fields
    NO_CAMEL = b'auto_camel_case=False'
    FRAMEWORK = 'strawberry'

    def __init__(self, workspace):
        super().__init__(workspace)
        self._names = QualifiedNames(workspace)

    def collect(self) -> Extraction:
        sources = [s for s in self.workspace.sources if s.mentions(self.LIBRARY.encode())]
        schemas = [(s, c) for s in sources for c in PythonSyntax.walk(s.root, ('call',)) if self._schema(s, c)]
        roots = {(src.path, cls.start_byte) for _, src, cls in self._roots(schemas)}
        camel = not any(self.NO_CAMEL in call.text for _, call in schemas)
        routes = []
        for source in sources:
            for cls in PythonSyntax.walk(source.root, PythonSyntax.CLASS):
                named_root = PythonSyntax.name(cls).lower() in self.ROOTS
                if self._decorated(source, cls, self.TYPE) and (named_root or (source.path, cls.start_byte) in roots):
                    routes += self._fields(source, cls, camel)
        return Extraction(routes=routes)

    def _schema(self, source, call):
        return self._is(source, call.child_by_field_name('function'), self.SCHEMA)

    def _is(self, source, node, dotted):
        return QualifiedNames.matches(self._names.of(source, node), self.LIBRARY, dotted)

    def _roots(self, schemas):
        """(keyword, source, class) of the root types the schemas name."""
        for source, call in schemas:
            _, kw = PythonSyntax.call_args(call)
            for key in self.ROOTS & set(kw):
                found = self.workspace.names.expression(source, kw[key])
                if found is not None and found.is_class:
                    yield key, found.source, found.node

    def _decorated(self, source, node, dotted):
        """Whether a definition carries `@strawberry.<dotted>` (called or not)."""
        parent = node.parent
        if parent is None or parent.type != 'decorated_definition':
            return False
        for d in parent.children:
            expr = d.named_children[0] if d.type == 'decorator' and d.named_children else None
            if expr is not None and expr.type == 'call':
                expr = expr.child_by_field_name('function')
            if expr is not None and self._is(source, expr, dotted):
                return True
        return False

    def _fields(self, source, cls, camel):
        out = []
        for st in cls.child_by_field_name('body').named_children:
            if st.type == 'decorated_definition':
                func = st.child_by_field_name('definition')
                if func.type == 'function_definition' and any(self._decorated(source, func, f) for f in self.FIELDS):
                    out.append(self._route(source, cls, func, PythonSyntax.name(func), self._renamed(st), camel))
            elif st.type == 'expression_statement':
                out += [self._route(source, cls, a, name, '', camel) for a, name in self._attributes(st)]
        return out

    def _attributes(self, statement):
        """(node, name) of `name: T` and `name: T = strawberry.field(...)` attributes that are fields."""
        for a in statement.named_children:
            left, annotation = a.child_by_field_name('left'), a.child_by_field_name('type')
            if a.type != 'assignment' or annotation is None or left.type != 'identifier':
                continue
            if not (PythonSyntax.identifiers(annotation) & self.HIDDEN) and not PythonSyntax.text(left).startswith('_'):
                yield a, PythonSyntax.text(left)

    @staticmethod
    def _renamed(decorated):
        """The `name=` a field decorator gives, or ''."""
        for d in decorated.children:
            expr = d.named_children[0] if d.type == 'decorator' and d.named_children else None
            if expr is not None and expr.type == 'call':
                name = PythonSyntax.call_args(expr)[1].get('name')
                if name is not None and name.type == 'string':
                    return PythonSyntax.text(name).strip('\'"')
        return ''

    def _route(self, source, cls, node, name, renamed, camel):
        field = renamed or (self.camel_case(name) if camel else name)
        handler = f'{PythonSyntax.name(cls)}.{name}'
        route = self.route(source, PythonSyntax.line(node), '/' + field, {ANY}, handler)
        return dataclasses.replace(route, framework=self.FRAMEWORK, protocol=Protocol.GRAPHQL)

    @staticmethod
    def camel_case(name):
        """Strawberry's to_camel_case: 'book_room' -> 'bookRoom' (each later part capitalised)."""
        first, *rest = name.split('_')
        return first + ''.join(part.capitalize() if part else '_' for part in rest)
