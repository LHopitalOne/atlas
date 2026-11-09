"""Reading javascript / typescript nodes: casts around expressions, call arguments, object keys, receiver names."""

from ...kit import StringTemplate, Syntax


class JsSyntax(Syntax):
    """Syntax helpers shared by the javascript, typescript and tsx grammars."""

    # expressions that only wrap another one: `(x)`, `x as T`, `x satisfies T`, `x!`, `await x`
    WRAPPERS = frozenset(
        {'parenthesized_expression', 'as_expression', 'satisfies_expression', 'non_null_expression', 'await_expression'}
    )
    CASTS = WRAPPERS | {'type_assertion'}  # `<string>u` keeps its expression as the last child
    DECLARATIONS = frozenset({'lexical_declaration', 'variable_declaration'})  # const / let / var
    PARAMETERS = frozenset({'required_parameter', 'optional_parameter'})  # typescript parameters
    NAMED = frozenset({'identifier', 'property_identifier', 'this'})
    MAX_DEPTH = 5  # how far a receiver or callee chain is followed

    @classmethod
    def unwrap(cls, node):
        """The expression inside parentheses, casts, `!` and `await`."""
        while node is not None and node.type in cls.CASTS and node.named_children:
            node = node.named_children[-1] if node.type == 'type_assertion' else node.named_children[0]
        return node

    @classmethod
    def outer_parent(cls, node):
        """The first parent of `node` that does not only wrap it (parentheses, casts, `await`...), or None."""
        parent = node.parent
        while parent is not None and parent.type in cls.WRAPPERS:
            parent = parent.parent
        return parent

    @staticmethod
    def args(call):
        """The arguments of a call or `new` expression, without comments."""
        a = call.child_by_field_name('arguments')
        if a is None or a.type != 'arguments':
            return []
        return [x for x in a.named_children if x.type != 'comment']

    @staticmethod
    def string(node):
        """The value of a string or template literal, interpolations written as {name}; None for anything else."""
        return StringTemplate.of(node)

    @classmethod
    def prop(cls, obj, key):
        """The value of `key` in an object literal."""
        obj = cls.unwrap(obj)
        if obj is None or obj.type != 'object':
            return None
        for p in obj.named_children:
            if p.type == 'pair':
                k = p.child_by_field_name('key')
                name = StringTemplate.of(k) if k.type == 'string' else cls.text(k)
                if name == key:
                    return p.child_by_field_name('value')
            elif p.type == 'shorthand_property_identifier' and cls.text(p) == key:
                return p
        return None

    @classmethod
    def require(cls, node):
        """The module of `require('./module')`, or None."""
        node = cls.unwrap(node)
        if node is None or node.type != 'call_expression':
            return None
        if cls.text(node.child_by_field_name('function')) != 'require':
            return None
        args = cls.args(node)
        return StringTemplate.of(cls.unwrap(args[0])) if args and cls.unwrap(args[0]).type == 'string' else None

    @staticmethod
    def contains(outer, inner):
        return outer.start_byte <= inner.start_byte and inner.end_byte <= outer.end_byte

    @classmethod
    def names_in(cls, node):
        """Identifiers and member chains in an expression ('settings.API_URL', 'BASE')."""
        out = set()
        for n in cls.walk(node, {'identifier', 'member_expression'}):
            if n.parent is not None and n.parent.type == 'member_expression':
                continue
            out.add(cls.text(n))
        return out

    @classmethod
    def last_name(cls, node):
        """The name a receiver ends in: `this.apiClient` -> 'apiClient', `request(app)` -> 'request'."""
        for _ in range(cls.MAX_DEPTH):
            node = cls.unwrap(node)
            if node is None:
                return ''
            if node.type == 'call_expression':
                node = node.child_by_field_name('function')
            elif node.type == 'member_expression':
                return cls.text(node.child_by_field_name('property'))
            elif node.type in cls.NAMED:
                return cls.text(node)
            else:
                return ''
        return ''

    @classmethod
    def callee_head(cls, fn):
        """The leftmost name of a callee: `describe.each([...])` -> 'describe'; '' for a function expression."""
        for _ in range(cls.MAX_DEPTH):
            if fn is None:
                return ''
            if fn.type == 'identifier':
                return cls.text(fn)
            if fn.type == 'member_expression':
                fn = fn.child_by_field_name('object')
            elif fn.type == 'call_expression':
                fn = fn.child_by_field_name('function')
            else:
                return ''
        return ''
