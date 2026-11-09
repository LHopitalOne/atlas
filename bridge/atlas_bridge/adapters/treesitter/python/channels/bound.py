"""The expressions a name or a dotted name holds where it is read, and the scope a function is read in for one call."""

from ..calls import CallSite
from ..scope import Binding, Scope
from ..syntax import PythonSyntax
from .objects import Field
from .origins import Origins
from .sites import FunctionSites


class BoundValues:
    """A name is its last assignment in the function before the use; a parameter is what the call the scope is read
    for passes, else what each call site passes (and its default); anything else is the module-level value. A dotted
    name is a module's value or `settings.NAME` (django.conf's settings object)."""

    SETTINGS = 'settings'

    def __init__(self, workspace, sites):
        self._workspace = workspace
        self._sites = sites  # FunctionSites

    def of(self, node, scope) -> list[Field]:
        """What an identifier or attribute node may hold, as expressions to read further."""
        if node.type == 'attribute':
            return self._attribute(node, scope)
        if node.type != 'identifier':
            return []
        name, func = PythonSyntax.text(node), scope.func
        if func is not None:
            prior = self._workspace.locals.before(scope.source, func, name, node.start_byte)
            if prior:
                return [Field(prior[-1].value, scope)]
            if name in PythonSyntax.param_names(func):
                return self._parameter(name, scope)
        found = self._workspace.names.lookup(scope.source, name, before=node.start_byte if func is None else None)
        return [Field(found.node, Scope.module(found.source))] if found is not None and found.is_value else []

    def _parameter(self, name, scope):
        bound = scope.bound(name)
        if bound is not None or scope.called:
            return [Field(bound.node, bound.scope)] if bound is not None else []
        out = [Field(site.bound[name], site.scope) for site in self._sites.of(scope) if name in site.bound]
        default = dict(PythonSyntax.params(scope.func)).get(name)
        return out + ([Field(default, scope.without_function())] if default is not None else [])

    def _attribute(self, node, scope):
        owner = node.child_by_field_name('object')
        attr = PythonSyntax.text(node.child_by_field_name('attribute'))
        if PythonSyntax.is_self(owner) and scope.cls is not None:
            value = self._workspace.attributes.own(scope.source, scope.cls).get(attr)
            if value is not None:
                return [Field(value, scope.without_function())]
            return [Field(v, Scope.at(scope.source, v)) for v, _ in Origins.assignments(scope.cls, attr) if v]
        if owner.type == 'identifier' and PythonSyntax.text(owner) == self.SETTINGS:
            found = self._workspace.settings.value(attr)
            return [Field(found[1], Scope.module(found[0]))] if found is not None else []
        found = self._workspace.names.value(scope.source, node)
        return [Field(found.node, Scope.module(found.source))] if found is not None else []

    def called(self, call, scope) -> tuple | None:
        """(function node, the scope its body is read in for this call) of a call to a function or `self` method of
        this repository, or None. The scope binds each parameter to the argument the call passes, or its default."""
        fn = call.child_by_field_name('function')
        if fn.type == 'attribute' and PythonSyntax.is_self(fn.child_by_field_name('object')):
            method = Origins.method(scope.cls, PythonSyntax.text(fn.child_by_field_name('attribute')))
            found = (scope.source, method) if method is not None else None
        else:
            symbol = (
                self._workspace.names.expression(scope.source, fn) if fn.type in ('identifier', 'attribute') else None
            )
            found = (symbol.source, symbol.node) if symbol is not None and symbol.is_function else None
        if found is None:
            return None
        source, func = found
        params = FunctionSites.params(func)
        site = CallSite.at(scope.source, call, params)
        if site.splat:
            return None
        cls = PythonSyntax.ancestor(func, PythonSyntax.CLASS)
        bindings = [Binding(name, node, site.scope) for name, node in site.bound.items()]
        outside = Scope(source, None, cls)
        bindings += [
            Binding(name, value, outside) for name, value in params if value is not None and name not in site.bound
        ]
        return func, Scope(source, func, cls, tuple(bindings), called=True)
