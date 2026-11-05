"""The value of a URL expression as a template: literals, template strings, `+`, bindings, URL builders."""

from ...kit import StringTemplate, ValueResolver
from ..bindings.scopes import Scopes
from ..syntax.nodes import JsSyntax
from .urls import UrlText


class UrlValues(ValueResolver):
    """Resolves URL expressions of one file. The scope passed along is the set of hints the expression adds to (names
    of variables and settings it reads). Each binding is resolved once per file."""

    HANDLERS = {
        'string': '_string',
        'template_string': '_template',
        'binary_expression': '_binary',
        'ternary_expression': '_ternary',
        'identifier': '_identifier',
        'number': '_number',
        'call_expression': '_builder',
        'new_expression': '_url_object',
    }
    TEMPLATE_TEXT = frozenset({'string_fragment', 'escape_sequence'})
    FALLBACKS = frozenset({'||', '??'})
    MAX_URL = 1000  # a resolved URL longer than this is not a URL

    def __init__(self, scopes: Scopes):
        self._scopes = scopes
        self._resolved = {}  # initializer node id -> (value, hints)

    def resolve(self, node, scope, depth=0):
        return super().resolve(JsSyntax.unwrap(node), scope, depth)

    def unknown(self, node, scope):
        scope.add(JsSyntax.text(node))
        return self._placeholder(node)

    @staticmethod
    def _placeholder(node):
        return '{' + StringTemplate.placeholder(JsSyntax.text(node)) + '}'

    def _string(self, node, hints, depth):
        return JsSyntax.string(node)

    def _number(self, node, hints, depth):
        return JsSyntax.text(node)

    def _template(self, node, hints, depth):
        out = ''
        for c in node.children:
            if c.type in self.TEMPLATE_TEXT:
                out += JsSyntax.text(c)
            elif c.type == 'template_substitution':
                inner = c.named_children
                part = self.resolve(inner[0], hints, depth) if inner else '{param}'
                out = UrlText.join(out, part, inner[0] if inner else None)
        return out

    def _binary(self, node, hints, depth):
        op = JsSyntax.text(node.child_by_field_name('operator'))
        right_node = node.child_by_field_name('right')
        left = self.resolve(node.child_by_field_name('left'), hints, depth)
        right = self.resolve(right_node, hints, depth)
        if op == '+':
            return UrlText.join(left, right, right_node)
        if op in self.FALLBACKS:
            return left if UrlText.literal(left) or not UrlText.literal(right) else right
        return self._placeholder(node)

    def _ternary(self, node, hints, depth):
        return self.resolve(node.child_by_field_name('consequence'), hints, depth)

    def _builder(self, node, hints, depth):
        """A URL builder: getUrl('/orders/$id/', {...}) is the path it is given."""
        args = JsSyntax.args(node)
        first = JsSyntax.unwrap(args[0]) if args else None
        if first is not None and first.type in ('string', 'template_string'):
            value = self.resolve(first, hints, depth)
            if UrlText.path_like(value):
                hints.add(JsSyntax.text(node.child_by_field_name('function')))
                return value
        return self.unknown(node, hints)

    def _url_object(self, node, hints, depth):
        """`new URL(path, base)` is its path; the base names the host."""
        args = JsSyntax.args(node)
        if JsSyntax.text(node.child_by_field_name('constructor')) != 'URL' or not args:
            return self.unknown(node, hints)
        for a in args[1:]:
            hints.add(JsSyntax.text(a))
            if JsSyntax.unwrap(a).type == 'identifier':
                self.resolve(a, hints, depth)
        return self.resolve(args[0], hints, depth)

    def _identifier(self, node, hints, depth):
        """The value bound to an identifier, or {name}."""
        name = JsSyntax.text(node)
        hints.add(name)
        value = self._scopes.lookup(node, name) if depth < self.MAX_DEPTH else None
        if value is not None:
            cached = self._resolved.get(value.id)
            if cached is None:
                found = {JsSyntax.text(value)}
                resolved = self.resolve(value, found, depth + 1)
                cached = self._resolved[value.id] = (resolved, found)
            resolved, found = cached
            hints.update(found)
            if UrlText.literal(resolved) and len(resolved) <= self.MAX_URL:
                return resolved
        return '{' + name + '}'
