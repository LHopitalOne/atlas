"""Where an object comes from: the calls that made it and the type annotations that name it, followed through
locals, `with ... as` names, parameters (their annotation and what callers pass), `self` attributes, properties,
module-level names and the functions that return it."""

from typing import NamedTuple

from ..scope import Scope
from ..syntax import PythonSyntax
from .receivers import MethodCallers
from .sites import FunctionSites


class Origin(NamedTuple):
    """A call that made the object, or an annotation that names its type, and the scope it is read in."""

    CALL, ANNOTATION = 'call', 'annotation'

    kind: str
    node: object
    scope: Scope

    @property
    def is_call(self):
        return self.kind == self.CALL


class Origins:
    """The Origins of an expression, at most MAX_DEPTH steps away and MAX_ORIGINS in all."""

    MAX_DEPTH = 6
    MAX_ORIGINS = 8
    WRAPPERS = frozenset({'await', 'parenthesized_expression'})
    PROPERTIES = frozenset({'property', 'cached_property', 'functools.cached_property'})

    def __init__(self, workspace):
        self._workspace = workspace
        self.sites = FunctionSites(workspace, MethodCallers(workspace, self))
        self._handlers = {'call': self._call, 'identifier': self._identifier, 'attribute': self._attribute}

    def of(self, node, scope, depth=0) -> list[Origin]:
        if node is None or depth > self.MAX_DEPTH:
            return []
        if node.type in self.WRAPPERS:
            return self.of(node.named_children[0] if node.named_children else None, scope, depth + 1)
        handler = self._handlers.get(node.type)
        return handler(node, scope, depth)[: self.MAX_ORIGINS] if handler is not None else []

    def _call(self, node, scope, depth):
        """The call itself, then what the function it calls in this repository returns."""
        out = [Origin(Origin.CALL, node, scope)]
        found = self.function(node.child_by_field_name('function'), scope)
        if found is not None:
            out += self._returned(*found, depth)
        return out

    def function(self, fn, scope):
        """(source, function node) a callee names in this repository: `name`, `module.name`, `self.method` or
        `Class.method` (a classmethod or staticmethod: `Settings.from_env()`)."""
        if fn.type == 'attribute' and PythonSyntax.is_self(fn.child_by_field_name('object')):
            method = self.method(scope.cls, PythonSyntax.text(fn.child_by_field_name('attribute')))
            return (scope.source, method) if method is not None else None
        found = self._workspace.names.expression(scope.source, fn) if fn.type in ('identifier', 'attribute') else None
        if found is None and fn.type == 'attribute':
            return self._class_method(fn, scope)
        return (found.source, found.node) if found is not None and found.is_function else None

    def _class_method(self, fn, scope):
        """(source, method node) of `Class.method` for a class of this repository, or None."""
        owner = self._workspace.names.expression(scope.source, fn.child_by_field_name('object'))
        if owner is None or not owner.is_class:
            return None
        method = self.method(owner.node, PythonSyntax.text(fn.child_by_field_name('attribute')))
        return (owner.source, method) if method is not None else None

    @staticmethod
    def method(cls, name):
        """The function definition `name` in a class body, or None."""
        body = cls.child_by_field_name('body') if cls is not None else None
        for st in body.named_children if body is not None else ():
            st = st.child_by_field_name('definition') if st.type == 'decorated_definition' else st
            if st is not None and st.type == 'function_definition' and PythonSyntax.name(st) == name:
                return st
        return None

    def _returned(self, source, func, depth):
        """The return annotation of a function and the expressions it returns."""
        out = []
        annotation = func.child_by_field_name('return_type')
        if annotation is not None:
            out.append(Origin(Origin.ANNOTATION, annotation, Scope.at(source, func)))
        for r in PythonSyntax.body_nodes(func.child_by_field_name('body')):
            if r.type == 'return_statement' and r.named_children:
                out += self.of(r.named_children[0], Scope.at(source, r), depth + 1)
        return out

    def _identifier(self, node, scope, depth):
        name = PythonSyntax.text(node)
        func = scope.func
        if func is not None:
            prior = self._workspace.locals.before(scope.source, func, name, node.start_byte)
            bound = [a.value for a in prior[-1:]] + self._with_aliases(func, name, node.start_byte)
            if bound:
                return [o for value in bound for o in self.of(value, scope, depth + 1)]
            if name in PythonSyntax.param_names(func):
                return self._parameter(func, name, scope, depth)
        found = self._workspace.names.lookup(scope.source, name, before=node.start_byte if func is None else None)
        if found is not None and found.is_value:
            return self.of(found.node, Scope.module(found.source), depth + 1)
        return []

    @staticmethod
    def _with_aliases(func, name, before):
        """The values of `with value as name` in a function body, before a byte."""
        out = []
        for n in PythonSyntax.walk(func.child_by_field_name('body'), ('as_pattern',)):
            alias = n.child_by_field_name('alias')
            if n.end_byte <= before and alias is not None and PythonSyntax.text(alias) == name and n.named_children:
                out.append(n.named_children[0])
        return out

    def _parameter(self, func, name, scope, depth):
        """A parameter's annotation, then what the call the scope is read for passes, or else its default and what
        each call site passes for it."""
        out = [Origin(Origin.ANNOTATION, a, scope) for a in self._annotations(func, name)]
        bound = scope.bound(name)
        if bound is not None or scope.called:
            return out + (self.of(bound.node, bound.scope, depth + 1) if bound is not None else [])
        default = dict(PythonSyntax.params(func)).get(name)
        if default is not None:
            out += self.of(default, scope.without_function(), depth + 1)
        for site in self.sites.of(scope):
            if name in site.bound:
                out += self.of(site.bound[name], site.scope, depth + 1)
        return out

    @staticmethod
    def _annotations(func, name):
        params = func.child_by_field_name('parameters')
        for p in params.named_children if params is not None else ():
            kids = p.named_children
            label = p.child_by_field_name('name') or (kids[0] if kids else None)
            annotation = p.child_by_field_name('type')
            if annotation is not None and PythonSyntax.text(label) == name:
                yield annotation

    def _attribute(self, node, scope, depth):
        obj = node.child_by_field_name('object')
        if PythonSyntax.is_self(obj) and scope.cls is not None:
            return self._member(scope, PythonSyntax.text(node.child_by_field_name('attribute')), depth)
        found = self._workspace.names.value(scope.source, node)
        return self.of(found.node, Scope.module(found.source), depth + 1) if found is not None else []

    def _member(self, scope, attr, depth):
        """`self.attr`: every assignment of it in the class (value and annotation) and a property of that name."""
        out = []
        for value, annotation in self.assignments(scope.cls, attr):
            where = Scope.at(scope.source, value if value is not None else annotation)
            if annotation is not None:
                out.append(Origin(Origin.ANNOTATION, annotation, where))
            out += self.of(value, where, depth + 1)
        prop = self.method(scope.cls, attr)
        if prop is not None and self._is_property(prop):
            out += self._returned(scope.source, prop, depth)
        return out

    @staticmethod
    def assignments(cls, attr):
        """[(value, annotation)] of every `self.attr = value` (or `self.attr: T = value`) in a class."""
        out = []
        for n in PythonSyntax.walk(cls.child_by_field_name('body'), ('assignment',)):
            left = n.child_by_field_name('left')
            if (
                left.type == 'attribute'
                and PythonSyntax.is_self(left.child_by_field_name('object'))
                and PythonSyntax.text(left.child_by_field_name('attribute')) == attr
            ):
                out.append((n.child_by_field_name('right'), n.child_by_field_name('type')))
        return out

    def _is_property(self, func):
        parent = func.parent
        if parent is None or parent.type != 'decorated_definition':
            return False
        return any(
            PythonSyntax.text(d).lstrip('@') in self.PROPERTIES for d in parent.children if d.type == 'decorator'
        )
