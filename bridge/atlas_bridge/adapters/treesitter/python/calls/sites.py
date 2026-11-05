"""Hints a request site gives about the service it calls: the file, function, class, receiver and its origin."""

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
