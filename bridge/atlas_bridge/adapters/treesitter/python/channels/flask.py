"""Flask configuration: `app.config['KEY']` after `app.config.from_object(obj)` is obj's attribute KEY."""

from ..scope import Scope
from ..syntax import PythonSyntax
from .objects import Field


class FlaskConfig:
    """Flask's Config.from_object(obj) copies obj's uppercase attributes into the config mapping, so `X.config['KEY']`
    reads the class body of an object handed to `X.config.from_object` in the same function (or module)."""

    CONFIG = 'config'
    LOADER = 'from_object'

    def __init__(self, workspace):
        self._workspace = workspace

    def value(self, node, scope) -> Field | None:
        """What `X.config['KEY']` holds, or None."""
        mapping, key = node.child_by_field_name('value'), node.child_by_field_name('subscript')
        if mapping.type != 'attribute' or key is None or key.type != 'string':
            return None
        if PythonSyntax.text(mapping.child_by_field_name('attribute')) != self.CONFIG:
            return None
        name = PythonSyntax.text(key).strip('\'"')
        for obj in self._loaded(PythonSyntax.text(mapping), scope):
            for source, cls in self._classes(obj, scope):
                found = self._workspace.attributes.own(source, cls).get(name)
                if found is not None:
                    return Field(found, Scope(source, None, cls))
        return None

    def _loaded(self, config, scope):
        """The arguments of `<config>.from_object(arg)` calls in the function (or module) around the scope."""
        where = scope.func if scope.func is not None else scope.source.root
        for call in PythonSyntax.walk(where, ('call',)):
            fn = call.child_by_field_name('function')
            if fn.type != 'attribute' or PythonSyntax.text(fn.child_by_field_name('attribute')) != self.LOADER:
                continue
            pos, _ = PythonSyntax.call_args(call)
            if pos and PythonSyntax.text(fn.child_by_field_name('object')) == config:
                yield pos[0]

    def _classes(self, node, scope):
        """[(source, class)] an argument names: a class, or a parameter whose default is one."""
        if node.type == 'identifier' and scope.func is not None:
            default = dict(PythonSyntax.params(scope.func)).get(PythonSyntax.text(node))
            node = default if default is not None else node
        found = (
            self._workspace.names.expression(scope.source, node) if node.type in ('identifier', 'attribute') else None
        )
        return [(found.source, found.node)] if found is not None and found.is_class else []
