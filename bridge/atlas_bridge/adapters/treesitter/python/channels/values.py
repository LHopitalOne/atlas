"""ChannelValues: the Python value resolver, reading further for channel names and ports: environment defaults,
number conversions, fields of this repository's objects and `self` attributes set from constructor arguments."""

from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker, PythonValueResolver, Value
from .bound import BoundValues
from .enums import EnumMembers
from .flask import FlaskConfig
from .mappings import MappingEntries
from .objects import Field, ObjectFields
from .origins import Origins
from .qualified import QualifiedNames
from .sites import FunctionSites


class ChannelValues(PythonValueResolver):
    """The URL resolver with what a channel's value is often read through. `os.getenv(name, default)` and
    `os.environ.get(name, default)` read as their default, `int(x)` and `float(x)` as x. An attribute the URL resolver
    cannot read is a field of an object (ObjectFields) or, on `self`, what a method assigned it; a parameter there is
    settled with what the function's call sites pass (settle()). An integer literal (a port) is its digits. Dict
    literals are read by key (MappingEntries: `M['k']`, `make()['k']`, `M.get(k, d)`) and enum members by value
    (EnumMembers: `Topic.EVENTS.value`)."""

    HANDLERS = {**PythonValueResolver.HANDLERS, 'integer': 'integer'}
    ENVIRONMENT = frozenset({'os.getenv', 'os.environ.get'})  # (name, default): the default when the name is unset
    NUMBERS = frozenset({'int', 'float'})
    MAX_ALTS = 4
    MAX_CHANNELS = 32  # the channels one send or receive may name: a helper called with a different name at each site

    def __init__(self, workspace):
        super().__init__(workspace)
        self.origins = Origins(workspace)
        self._names = QualifiedNames(workspace)
        self._objects = ObjectFields(workspace, self.origins)
        self._config = FlaskConfig(workspace)
        self._sites = self.origins.sites
        bound = BoundValues(workspace, self._sites)
        self._mappings = MappingEntries(workspace, self, bound)
        self._enums = EnumMembers(workspace, self, bound, self._mappings)

    @staticmethod
    def integer(node, scope, depth):
        return [Value(PythonSyntax.text(node))]

    def identifier(self, node, scope, depth):
        """A name a nested function reads from the function around it (a closure) is read there, settled with what
        that function's call sites pass."""
        outer = self._closure(node, scope)
        if outer is not None and depth < self.MAX_DEPTH:
            return self.settled(node, outer, depth + 1, self.MAX_CHANNELS) or self.unknown(node)
        return super().identifier(node, scope, depth)

    def _closure(self, node, scope):
        """The scope of the enclosing function that binds a name the function around `scope` neither assigns nor
        takes as a parameter, or None."""
        func, name = scope.func, PythonSyntax.text(node)
        if func is None or name in PythonSyntax.param_names(func):
            return None
        if name in self._workspace.locals.assignments_in(scope.source, func):
            return None
        outer = PythonSyntax.ancestor(func, PythonSyntax.FUNCTION)
        if outer is None:
            return None
        if name in PythonSyntax.param_names(outer) or name in self._workspace.locals.assignments_in(
            scope.source, outer
        ):
            return Scope.at(scope.source, func)
        return None

    def call(self, node, scope, depth):
        fn = node.child_by_field_name('function')
        pos, kw = PythonSyntax.call_args(node)
        if self._names.of(scope.source, fn) in self.ENVIRONMENT:
            default = pos[1] if len(pos) > 1 else kw.get('default')
            return self.resolve(default, scope, depth + 1) if default is not None else self.unknown(node)
        if fn.type == 'identifier' and PythonSyntax.text(fn) in self.NUMBERS and len(pos) == 1:
            return self.resolve(pos[0], scope, depth + 1)
        entries = self._mappings.get(node, scope)
        if entries is not None:
            return self._read(entries, depth) or self.unknown(node)
        return super().call(node, scope, depth)

    def attribute(self, node, scope, depth):
        found = super().attribute(node, scope, depth)
        if any(v.is_known for v in found) or depth >= self.MAX_DEPTH:
            return found
        members = self._read(self._enums.value(node, scope), depth)
        if members:
            return members
        if PythonSyntax.is_self(node.child_by_field_name('object')):
            fields = self._self_fields(node, scope)
        else:
            fields = self._objects.of(node, scope)
        out = [v for f in fields for v in self.settled(f.node, f.scope, depth + 1)]
        return [v for v in out if v.is_literal][: self.MAX_ALTS] or found

    def _self_fields(self, node, scope):
        attr = PythonSyntax.text(node.child_by_field_name('attribute'))
        if scope.cls is None:
            return []
        return [Field(v, Scope.at(scope.source, v)) for v, _ in self.origins.assignments(scope.cls, attr) if v]

    def subscript(self, node, scope, depth):
        found = super().subscript(node, scope, depth)
        if any(v.is_known for v in found) or depth >= self.MAX_DEPTH:
            return found
        value = self._config.value(node, scope)
        if value is not None:
            return self.resolve(value.node, value.scope, depth + 1)
        return self._read(self._mappings.subscript(node, scope), depth) or found

    def _read(self, fields, depth) -> list[Value]:
        """The known values of the expressions in `fields`."""
        out = [v for f in fields for v in self.resolve(f.node, f.scope, depth + 1) if v.is_known]
        return out[: self.MAX_ALTS]

    def settled(self, node, scope, depth=0, limit=MAX_ALTS) -> list[Value]:
        """The values of `node` with the parameters of the function around `scope` replaced by what its call sites
        pass, followed up while the depth lasts, at most `limit` of them. A value still holding a parameter is
        dropped."""
        return self.settle(self.resolve(node, scope, depth), scope, depth, limit)

    def settle(self, values, scope, depth, limit=MAX_ALTS) -> list[Value]:
        out = []
        for v in values:
            names = sorted(Marker.names(v.text))
            if not names:
                out.append(v)
            elif scope.func is not None and depth < self.MAX_DEPTH:
                for site in self._sites.of(scope, max(limit, FunctionSites.MAX_SITES)):
                    out += self._at_site(v, names, site, scope, depth, limit)
        return out[:limit]

    def _at_site(self, value, names, site, scope, depth, limit):
        """The value with each parameter filled with what one call site passes (or the parameter's default)."""
        texts = [value.text]
        defaults = dict(FunctionSites.params(scope.func))
        for name in names:
            if name in site.bound:
                options = self.settled(site.bound[name], site.scope, depth + 1, limit)
            elif defaults.get(name) is not None:
                options = self.resolve(defaults[name], scope.without_function(), depth + 1)
            else:
                return []
            texts = [t.replace(Marker.wrap(name), o.text) for t in texts for o in options if o.is_literal]
        return [Value(t, value.hints) for t in texts[:limit]]
