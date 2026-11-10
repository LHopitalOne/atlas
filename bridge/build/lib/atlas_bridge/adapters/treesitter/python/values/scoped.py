"""The base of the Python resolver: names read where they are used (locals, parameters, module constants, imports and
class attributes), parentheses and conditional expressions."""

import itertools
from abc import abstractmethod

from ...kit import StringTemplate, ValueResolver
from ..scope import Scope
from ..syntax import PythonSyntax
from .value import Marker, Value


class ScopeResolver(ValueResolver):
    """The values of names and dotted names, read where they are used: a function's locals and parameters, then the
    module's constants and imports. Parentheses and `a if c else b` resolve to their parts.

    Abstract: a concrete resolver adds the handlers for literals and the expressions built from them, and string().
    """

    HANDLERS = {
        'parenthesized_expression': 'parenthesized',
        'conditional_expression': 'conditional',
        'identifier': 'identifier',
        'attribute': 'attribute',
        'subscript': 'subscript',
    }
    SETTINGS = 'settings'  # `settings.NAME`: django.conf's settings object
    MAX_DEPTH = 14
    MAX_ALTS = 4  # alternatives one expression may resolve to

    def __init__(self, workspace):
        self._workspace = workspace

    @abstractmethod
    def string(self, node, scope, depth=0) -> Value:
        """The one Value of a string literal (or of implicitly concatenated literals)."""

    def unknown(self, node, scope=None):
        if node is None:
            return [Value('{param}', frozenset(), Value.UNKNOWN)]
        return [self.opaque(node)]

    @staticmethod
    def opaque(node):
        """A value nothing is known about: a placeholder named after the expression, which it keeps as a hint."""
        t = PythonSyntax.text(node)
        return Value('{' + StringTemplate.placeholder(t) + '}', frozenset({Value.hint(t)}), Value.UNKNOWN)

    @classmethod
    def join(cls, left, right):
        """Every concatenation of a left and a right value, at most MAX_ALTS."""
        out = []
        for a, b in itertools.product(left, right):
            kind = Value.UNKNOWN if a.is_unknown and b.is_unknown else Value.LITERAL
            out.append(Value(a.text + b.text, a.hints | b.hints, kind))
        return out[: cls.MAX_ALTS]

    def parenthesized(self, node, scope, depth):
        if node.named_children:
            return self.resolve(node.named_children[0], scope, depth + 1)
        return self.unknown(node)

    def conditional(self, node, scope, depth):
        kids = node.named_children
        if len(kids) != 3:
            return self.unknown(node)
        return (self.resolve(kids[0], scope, depth + 1) + self.resolve(kids[2], scope, depth + 1))[: self.MAX_ALTS]

    def identifier(self, node, scope, depth):
        """A local's last assignment before the use, a parameter's marker, else the module-level name."""
        prior = self._prior(node, scope)
        return self._assigned(scope, prior, depth) if prior else self._unassigned(node, scope, depth)

    def interpolated_identifier(self, node, scope, depth):
        """A name inside an f-string: a local assigned more than once stays a placeholder named after it."""
        prior = self._prior(node, scope)
        if prior and len(self._locals(node, scope)) > 1:
            name = PythonSyntax.text(node)
            return [Value('{' + name + '}', frozenset({name}), Value.UNKNOWN)]
        return self.identifier(node, scope, depth)

    def _locals(self, node, scope):
        """Every assignment of the name in the enclosing function, in source order."""
        if scope.func is None:
            return []
        return self._workspace.locals.assignments_in(scope.source, scope.func).get(PythonSyntax.text(node), [])

    def _prior(self, node, scope):
        return [a for a in self._locals(node, scope) if a.end <= node.start_byte]

    def _unassigned(self, node, scope, depth):
        name = PythonSyntax.text(node)
        func = scope.func
        if func is not None and name in PythonSyntax.param_names(func):
            return [Value(Marker.wrap(name), frozenset(), Value.PARAM)]
        before = node.start_byte if func is None else None
        found = self._workspace.names.lookup(scope.source, name, before=before)
        if found and found.is_value:
            return self.resolve(found.node, Scope.module(found.source), depth + 1)
        return self.unknown(node)

    def _assigned(self, scope, prior, depth):
        """The last plain assignment, extended by the `+=` that follow it."""
        k = max((i for i, a in enumerate(prior) if not a.augmented), default=0)
        vs = self.resolve(prior[k].value, scope, depth + 1)
        for a in prior[k + 1 :]:
            if a.augmented:
                vs = self.join(vs, self.resolve(a.value, scope, depth + 1))
        return vs

    def attribute(self, node, scope, depth):
        setting = self._setting(node)
        if setting is not None:
            text = PythonSyntax.text(node)
            values = self.resolve(setting[1], Scope.module(setting[0]), depth + 1)
            return [Value(v.text, v.hints | {text}, v.kind) for v in values]
        if PythonSyntax.is_self(node.child_by_field_name('object')):
            attr = PythonSyntax.text(node.child_by_field_name('attribute'))
            cls = scope.cls
            value = self._workspace.attributes.own(scope.source, cls).get(attr) if cls is not None else None
            return self.resolve(value, scope.without_function(), depth + 1) if value is not None else self.unknown(node)
        found = self._workspace.names.value(scope.source, node)
        if found is not None:
            return self.resolve(found.node, Scope.module(found.source), depth + 1)
        return self.unknown(node)

    def _setting(self, node):
        """(source, value node) of `settings.NAME`, or None for any other attribute."""
        owner = node.child_by_field_name('object')
        if owner.type != 'identifier' or PythonSyntax.text(owner) != self.SETTINGS:
            return None
        return self._workspace.settings.value(PythonSyntax.text(node.child_by_field_name('attribute')))

    def subscript(self, node, scope, depth):
        """`MAPPING['key']` of a dict literal bound to a module-level name or a setting: that entry's value."""
        found = self._mapping(node.child_by_field_name('value'), scope)
        key = node.child_by_field_name('subscript')
        if found is None or key is None or key.type != 'string':
            return self.unknown(node)
        source, mapping = found
        wanted = self.string(key, scope).text
        for pair in mapping.named_children:
            k = pair.child_by_field_name('key') if pair.type == 'pair' else None
            if k is not None and k.type == 'string' and self.string(k, Scope.module(source)).text == wanted:
                text = PythonSyntax.text(node)
                values = self.resolve(pair.child_by_field_name('value'), Scope.module(source), depth + 1)
                return [Value(v.text, v.hints | {text}, v.kind) for v in values]
        return self.unknown(node)

    def _mapping(self, node, scope):
        """(source, dict literal node) a name, `module.NAME` or `settings.NAME` is bound to, or None."""
        if node is None:
            return None
        found = self._setting(node) if node.type == 'attribute' else None
        if found is None and node.type in ('identifier', 'attribute'):
            symbol = self._workspace.names.value(scope.source, node)
            found = (symbol.source, symbol.node) if symbol is not None else None
        return found if found is not None and found[1] is not None and found[1].type == 'dictionary' else None
