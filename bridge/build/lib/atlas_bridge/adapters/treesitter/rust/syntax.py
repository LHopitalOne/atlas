"""Reading Rust syntax: nodes that only wrap a value, call arguments, receivers, attributes and identifiers."""

from ..kit import Syntax


class RustSyntax(Syntax):
    """The kit's node helpers plus the Rust shapes every part of the extractor reads."""

    # Wrappers that hold the expression that matters: `(x)`, `x?`, `&x`, `x.await`.
    TRANSPARENT = frozenset({'parenthesized_expression', 'try_expression', 'reference_expression', 'await_expression'})
    STRINGS = frozenset({'string_literal', 'raw_string_literal'})
    NAMES = frozenset({'identifier', 'scoped_identifier'})
    IDENTIFIERS = frozenset({'identifier', 'field_identifier'})
    # Calls a receiver passes through on its way to being the client: `Client::builder().build().unwrap()`.
    RECEIVER_STEPS = frozenset({'unwrap', 'expect', 'build', 'clone', 'unwrap_or_default'})

    @classmethod
    def unwrap(cls, node):
        while node is not None and node.type in cls.TRANSPARENT:
            node = node.child_by_field_name('value') or (node.named_children[0] if node.named_children else None)
        return node

    @staticmethod
    def args(call):
        """A call's arguments, without comments."""
        a = call.child_by_field_name('arguments')
        return [c for c in a.named_children if 'comment' not in c.type] if a is not None else []

    @staticmethod
    def name(node):
        """The text of a node's `name` field: the name of a fn, mod or const."""
        return Syntax.text(node.child_by_field_name('name'))

    @staticmethod
    def method(call):
        """The field expression a method call goes through (`a.b(..)` -> `a.b`), or None for a plain call."""
        fn = call.child_by_field_name('function')
        return fn if fn is not None and fn.type == 'field_expression' else None

    @classmethod
    def is_concat(cls, node):
        return (
            node is not None
            and node.type == 'binary_expression'
            and cls.text(node.child_by_field_name('operator')) == '+'
        )

    @staticmethod
    def identifiers(node):
        """Every identifier and field name under `node`."""
        stack = [node]
        while stack:
            n = stack.pop()
            if n.type in RustSyntax.IDENTIFIERS:
                yield n
            stack.extend(n.children)

    @classmethod
    def chain_root(cls, node):
        """What a method chain starts from: `self.client.get(..)` -> `self`, `make().x()` -> `make`."""
        node = cls.unwrap(node)
        while node is not None:
            if node.type == 'call_expression':
                fn = node.child_by_field_name('function')
                if fn is None or fn.type != 'field_expression':
                    return fn
                node = cls.unwrap(fn.child_by_field_name('value'))
            elif node.type == 'field_expression':
                node = cls.unwrap(node.child_by_field_name('value'))
            else:
                return node
        return None

    @classmethod
    def receiver_name(cls, node):
        """The last name in a receiver: `self.client` -> 'client', `Client::new()` -> 'Client::new'."""
        node = cls.unwrap(node)
        while node is not None:
            if node.type == 'field_expression':
                return cls.text(node.child_by_field_name('field'))
            if node.type != 'call_expression':
                return cls.text(node)
            fn = node.child_by_field_name('function')
            if fn is None or fn.type != 'field_expression':
                return cls.text(fn)
            name = cls.text(fn.child_by_field_name('field'))
            if name not in cls.RECEIVER_STEPS:
                return name
            node = cls.unwrap(fn.child_by_field_name('value'))
        return ''
