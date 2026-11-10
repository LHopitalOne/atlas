"""Hints a request site gives about the service it calls: the file, function, class, receiver and its origin."""

from .....core.evidence import Assumption
from ..syntax import PythonSyntax
from ..values import Value


class SiteHints:
    """The words around a call site that may name the service it talks to."""

    ORIGIN = 300  # longest receiver origin kept

    def __init__(self, workspace):
        self._workspace = workspace

    def hints_for(self, scope, receiver):
        hints = {scope.source.path}
        if scope.func is not None:
            hints.add(PythonSyntax.name(scope.func))
        if scope.cls is not None:
            hints.add(PythonSyntax.name(scope.cls))
        if receiver is not None:
            hints.add(Value.hint(PythonSyntax.text(receiver)))
            origin = self.origin(scope, receiver)
            if origin:
                hints.add(origin[: self.ORIGIN])
        return frozenset(h for h in hints if h)

    def origin(self, scope, receiver):
        """The expression a client receiver was created from: `_pool = connection_from_url(settings.SNUBA)`."""
        node = receiver
        if node.type == 'attribute':
            obj = node.child_by_field_name('object')
            if PythonSyntax.is_self(obj):
                return self._self_origin(scope, node)
            found = self._workspace.names.value(scope.source, node)
            if found is not None:
                return PythonSyntax.text(found.node)
            while node.type == 'attribute':
                node = node.child_by_field_name('object')
        if node.type != 'identifier':
            return ''
        return self._name_origin(scope, PythonSyntax.text(node), receiver.start_byte)

    def _self_origin(self, scope, node):
        if not scope.cls:
            return ''
        attr = PythonSyntax.text(node.child_by_field_name('attribute'))
        value = self._workspace.attributes.attribute(scope.source, scope.cls, attr)
        return PythonSyntax.text(value) if value is not None else ''

    def _name_origin(self, scope, name, byte):
        if scope.func is not None:
            prior = self._workspace.locals.before(scope.source, scope.func, name, byte)
            if prior:
                return PythonSyntax.text(prior[-1].value)
        found = self._workspace.names.lookup(scope.source, name)
        return PythonSyntax.text(found.node) if found and found.is_value else ''

    def origin_assumption(self, scope, receiver):
        """The Assumption behind the receiver's origin when the finder looked it up by name: a module-level name
        (followed through imports) or an attribute of the enclosing class. None for a local variable, which the
        function itself shows, and for receivers with no origin."""
        if receiver is None:
            return None
        if receiver.type == 'attribute':
            obj, attr = receiver.child_by_field_name('object'), receiver.child_by_field_name('attribute')
            if PythonSyntax.is_self(obj):
                return self._attribute_assumption(scope, attr)
            found = self._workspace.names.value(scope.source, receiver)
            if found is not None:
                return self._name_assumption(scope, attr, found)
            while receiver.type == 'attribute':
                receiver = receiver.child_by_field_name('object')
        if receiver.type != 'identifier':
            return None
        name = PythonSyntax.text(receiver)
        if scope.func is not None and self._workspace.locals.before(
            scope.source, scope.func, name, receiver.start_byte
        ):
            return None
        found = self._workspace.names.lookup(scope.source, name)
        return self._name_assumption(scope, receiver, found) if found and found.is_value else None

    def _attribute_assumption(self, scope, attr):
        name = PythonSyntax.text(attr)
        if scope.cls is None or self._workspace.attributes.attribute(scope.source, scope.cls, name) is None:
            return None
        cls = scope.cls
        return Assumption(
            scope.source.path,
            PythonSyntax.line(attr),
            name,
            scope.source.path,
            PythonSyntax.line(cls),
            cls.end_point[0] + 1,
        )

    @staticmethod
    def _name_assumption(scope, name_node, symbol):
        """The name means the value assigned in symbol's file: the whole assignment statement's lines."""
        node = symbol.node
        if node.parent is not None and node.parent.type == 'assignment':
            node = node.parent
        return Assumption(
            scope.source.path,
            PythonSyntax.line(name_node),
            PythonSyntax.text(name_node),
            symbol.source.path,
            PythonSyntax.line(node),
            node.end_point[0] + 1,
        )
