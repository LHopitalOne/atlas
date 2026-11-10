"""AbsoluteUrl: whether a reverse() URL is made absolute, which is what handing it to another service takes."""

from ..syntax import PythonSyntax


class AbsoluteUrl:
    """A reverse() result counts as a URL for another service only when something puts a base in front of it:
    `"{}{}".format(prefix, reverse(...))`, `base + reverse(...)`, `f"{base}{reverse(...)}"`, `urljoin(base,
    reverse(...))` or `request.build_absolute_uri(reverse(...))`. A bare reverse() goes to a redirect, a template or
    a link on this service's own pages."""

    JOINS = frozenset({'format', 'urljoin'})  # the base comes first: reverse() must not be the first argument
    BUILDERS = frozenset({'build_absolute_uri', 'absolute_uri'})  # take a path and add a base
    THROUGH = frozenset({'argument_list', 'parenthesized_expression'})
    SCHEMES = ('http://', 'https://')
    MAX_UP = 4  # wrapping nodes climbed from reverse() to the expression that joins it

    @classmethod
    def made_absolute(cls, call) -> bool:
        """Whether the reverse() `call` is joined to a base URL in the expression around it."""
        node = call
        for _ in range(cls.MAX_UP):
            parent = node.parent
            if parent is None:
                return False
            if parent.type not in cls.THROUGH:
                return cls._joins(parent, node, call)
            node = parent
        return False

    @classmethod
    def _joins(cls, parent, child, call):
        if parent.type == 'call':
            return cls._joining_call(parent, call)
        if parent.type == 'binary_operator':
            return parent.child_by_field_name('right') == child
        if parent.type == 'interpolation':
            return cls._after_base(parent)
        return False

    @classmethod
    def _joining_call(cls, joiner, call):
        name = PythonSyntax.callee(joiner)
        if name in cls.BUILDERS:
            return True
        if name not in cls.JOINS:
            return False
        pos, _ = PythonSyntax.call_args(joiner)
        index = next((i for i, a in enumerate(pos) if a.start_byte <= call.start_byte < a.end_byte), 0)
        return index >= 1

    @classmethod
    def _after_base(cls, interpolation):
        """An f-string piece after another interpolation (the base) or after literal 'http(s)://...' text."""
        prev = interpolation.prev_named_sibling
        if prev is None:
            return False
        if prev.type == 'interpolation':
            return True
        return prev.type == 'string_content' and PythonSyntax.text(prev).startswith(cls.SCHEMES)
