"""The value of a URL expression as a template: literals, template strings, `+`, bindings, URL builders, URL objects
(`url.href`, `url.toString()`), helper functions and methods of the repository's classes that return a URL, and
members of object literals reached through destructuring and imports (`const { baseUrl } = config.api`)."""

from ...kit import StringTemplate, ValueResolver
from ..bindings.scopes import Scopes
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from .objects import ObjectPaths
from .urls import UrlText


class UrlValues(ValueResolver):
    """Resolves URL expressions of one file. The scope passed along is the set of hints the expression adds to (names
    of variables and settings it reads). Each binding is resolved once per file. A name or member chain bound to no
    value of its own here is followed to where its value is written (ObjectPaths), in this file or another."""

    HANDLERS = {
        'string': '_string',
        'template_string': '_template',
        'binary_expression': '_binary',
        'ternary_expression': '_ternary',
        'identifier': '_identifier',
        'shorthand_property_identifier': '_identifier',  # `{ url }`
        'number': '_number',
        'call_expression': '_call',
        'new_expression': '_url_object',
        'member_expression': '_member',
    }
    URL_PARTS = frozenset({'href', 'pathname'})  # properties of a URL object that hold the URL (or its path)
    TO_STRING = 'toString'
    FUNCTIONS = frozenset({'arrow_function', 'function_expression', 'function', 'function_declaration'})
    TEMPLATE_TEXT = frozenset({'string_fragment', 'escape_sequence'})
    FALLBACKS = frozenset({'||', '??'})
    MAX_URL = 1000  # a resolved URL longer than this is not a URL

    def __init__(self, scopes: Scopes, objects: ObjectPaths | None = None):
        self._scopes = scopes
        self._objects = objects
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

    def _call(self, node, hints, depth):
        """`url.toString()`, a helper function that returns a URL, or a URL builder."""
        fn = JsSyntax.unwrap(node.child_by_field_name('function'))
        if (
            fn is not None
            and fn.type == 'member_expression'
            and JsSyntax.text(fn.child_by_field_name('property')) == (self.TO_STRING)
        ):
            return self.resolve(fn.child_by_field_name('object'), hints, depth)
        returned = self._helper(fn, hints, depth) if fn is not None and fn.type == 'identifier' else None
        if returned is None and fn is not None and fn.type == 'member_expression':
            returned = self._method(fn, hints, depth)
        return returned if returned is not None else self._builder(node, hints, depth)

    def _method(self, fn, hints, depth):
        """What a method of a class of the repository returns, called on an instance (`desk.eventsUrl()`), when that
        is a URL with a known path."""
        found = self._objects.returned(fn) if self._objects is not None and depth < self.MAX_DEPTH else None
        if found is None:
            return None
        names = set()
        value = found.module.values.resolve(found.node, names, depth + 1)
        if not UrlText.literal(value) or not UrlText.path_like(value) or len(value) > self.MAX_URL:
            return None
        hints.add(JsSyntax.text(fn))
        hints.update(names)
        return value

    def _helper(self, fn, hints, depth):
        """What a function declared in this file returns (its parameters stay placeholders), when that is a URL."""
        bound = self._scopes.lookup(fn, JsSyntax.text(fn)) if depth < self.MAX_DEPTH else None
        if bound is None or bound.type not in self.FUNCTIONS:
            return None
        body = self._returned(bound)
        if body is None:
            return None
        found = set()
        value = self.resolve(body, found, depth + 1)
        if not UrlText.literal(value) or not UrlText.path_like(value):
            return None
        hints.add(JsSyntax.text(fn))
        hints.update(found)
        return value

    @staticmethod
    def _returned(fn):
        return Functions.returned(fn)

    def _member(self, node, hints, depth):
        """`url.href` / `url.pathname` of a URL object is that URL."""
        if JsSyntax.text(node.child_by_field_name('property')) in self.URL_PARTS:
            return self.resolve(node.child_by_field_name('object'), hints, depth)
        located = self._located(node, hints, depth)
        if located is not None:
            hints.add(JsSyntax.text(node))
            return located
        return self.unknown(node, hints)

    def _located(self, node, hints, depth):
        """The value of a name or member chain where it is written (an object property, an import), when that is a
        URL template with a known part; None otherwise."""
        found = self._objects.locate(node) if self._objects is not None and depth < self.MAX_DEPTH else None
        if found is None or found.node.id == node.id:
            return None
        names = set()
        value = found.module.values.resolve(found.node, names, depth + 1)
        if not UrlText.literal(value) or len(value) > self.MAX_URL:
            return None
        hints.update(names)
        return value

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
        else:
            located = self._located(node, hints, depth)
            if located is not None:
                return located
        return '{' + name + '}'
