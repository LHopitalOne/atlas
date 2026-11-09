"""What a call passes to a request helper: the values of an argument, and of a member the helper reads from an
options argument (`options.url` in `get(options) { $.ajax({ url: options.url }) }` called as `get({ url: '/x' })`)."""

import re
from dataclasses import dataclass

from ..bindings.binding import ValueBinding
from ..syntax.nodes import JsSyntax
from ..values.assignments import Assignments
from ..values.resolver import UrlValues


class ParamValues(UrlValues):
    """UrlValues of one file that keep a member of a function's parameter as '{param.key}', so the callers that
    give the parameter can fill it in."""

    PARAMETER_LISTS = frozenset({'formal_parameters', 'arrow_function'})

    def __init__(self, module):
        super().__init__(module.scopes, module.objects)
        self._module = module

    def _member(self, node, hints, depth):
        name = self.param_member(node)
        if name:
            hints.add(name)
            return '{' + name + '}'
        return super()._member(node, hints, depth)

    def param_member(self, node):
        """'options.url' for `options.url` where `options` is a parameter of the enclosing function; '' otherwise."""
        obj, key = JsSyntax.unwrap(node.child_by_field_name('object')), node.child_by_field_name('property')
        if obj is None or obj.type != 'identifier' or key is None or key.type != 'property_identifier':
            return ''
        if JsSyntax.text(key) in self.URL_PARTS:
            return ''  # `url.href` of a URL parameter is the URL itself
        return f'{JsSyntax.text(obj)}.{JsSyntax.text(key)}' if self.is_parameter(obj) else ''

    def is_parameter(self, name_node):
        """The name is bound by a parameter of a function (not a destructured const, a loop or catch variable)."""
        binding = self._module.scopes.binding(name_node, JsSyntax.text(name_node))
        if binding is None or isinstance(binding, ValueBinding):
            return False
        parent = binding.node.parent
        return parent is not None and parent.type in self.PARAMETER_LISTS


@dataclass(frozen=True)
class Member:
    """The values an options argument gives one key: none when it surely leaves the key out. `fallback` is the
    value it had before a spread parameter that may override it (`{ type: 'GET', ...options }`)."""

    values: tuple = ()
    fallback: str = ''


class Arguments:
    """Reads the arguments of calls in one file."""

    MEMBER = re.compile(r'^([A-Za-z_$][\w$]*)\.([A-Za-z_$][\w$]*)$')  # 'options.url': a member of a parameter
    SPREAD = 'spread_element'
    MAX_DEPTH = 4  # spreads and bindings followed

    def __init__(self, module):
        self._module = module
        self._values = ParamValues(module)
        self._assignments = Assignments()

    @property
    def values(self) -> ParamValues:
        return self._values

    def resolve(self, node, hints) -> list[str]:
        """The values an expression may hold: one, or one per value assigned to a `let` before it is read."""
        return [self._values.resolve(n, hints) for n in self._assignments.values(node)]

    def member(self, arg, key, hints, depth=0) -> Member | None:
        """The values `arg` gives `key` when it is an object literal, a const bound to one, or a parameter of the
        caller ('{param.key}'); None when nothing says."""
        arg = JsSyntax.unwrap(arg)
        if arg is None or depth > self.MAX_DEPTH:
            return None
        if arg.type == 'object':
            return self._scan(arg, key, hints, depth)
        if arg.type != 'identifier':
            return None
        if self._values.is_parameter(arg):
            return Member(('{' + JsSyntax.text(arg) + '.' + key + '}',))
        bound = JsSyntax.unwrap(self._module.scopes.lookup(arg, JsSyntax.text(arg)))
        return self._scan(bound, key, hints, depth) if bound is not None and bound.type == 'object' else None

    def _scan(self, obj, key, hints, depth):
        """Later properties override earlier ones; a spread that may hold the key leaves it open."""
        found = Member()
        for p in obj.named_children:
            if p.type == 'pair' and self._key(p) == key:
                found = Member(tuple(self.resolve(p.child_by_field_name('value'), hints)))
            elif p.type == 'shorthand_property_identifier' and JsSyntax.text(p) == key:
                found = Member(tuple(self.resolve(p, hints)))
            elif p.type == 'method_definition' and JsSyntax.text(p.child_by_field_name('name')) == key:
                return None
            elif p.type == self.SPREAD:
                found = self._spread(found, p, key, hints, depth)
                if found is None:
                    return None
        return found

    def _spread(self, found, spread, key, hints, depth):
        inner = spread.named_children[0] if spread.named_children else None
        given = self.member(inner, key, hints, depth + 1)
        if given is None or not given.values:
            return given if given is None else found
        if JsSyntax.unwrap(inner).type == 'identifier' and self._values.is_parameter(JsSyntax.unwrap(inner)):
            before = found.values[0] if len(found.values) == 1 else found.fallback
            return Member(given.values, before)  # the parameter may leave the key out
        return given

    @staticmethod
    def _key(pair):
        k = pair.child_by_field_name('key')
        return JsSyntax.string(k) if k.type == 'string' else JsSyntax.text(k)
