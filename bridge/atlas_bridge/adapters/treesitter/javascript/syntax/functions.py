"""Functions and classes around a node: their names, and whether a function returns a value."""

from .nodes import JsSyntax


class Functions:
    FUNCTIONS = frozenset(
        {
            'function_declaration',
            'generator_function_declaration',
            'function_expression',
            'function',
            'generator_function',
            'arrow_function',
            'method_definition',
        }
    )
    CLASSES = frozenset({'class_declaration', 'class', 'abstract_class_declaration'})
    FIELDS = frozenset({'field_definition', 'public_field_definition'})

    @classmethod
    def name(cls, fn):
        """A function's own name, or the name it is assigned to (variable, object key, member, class field)."""
        name = fn.child_by_field_name('name')
        if name is not None:
            return JsSyntax.text(name)
        parent = JsSyntax.outer_parent(fn)
        return cls._assigned_name(parent) if parent is not None else ''

    @classmethod
    def _assigned_name(cls, parent):
        if parent.type == 'variable_declarator':
            return JsSyntax.text(parent.child_by_field_name('name'))
        if parent.type == 'pair':
            return JsSyntax.text(parent.child_by_field_name('key'))
        if parent.type == 'assignment_expression':
            return JsSyntax.text(parent.child_by_field_name('left')).split('.')[-1]
        if parent.type in cls.FIELDS:
            return JsSyntax.text(parent.child_by_field_name('name') or parent.child_by_field_name('property'))
        return ''

    @staticmethod
    def returned(fn):
        """The expression a function returns: an arrow function's expression body, or its first `return` value."""
        body = fn.child_by_field_name('body')
        if body is None:
            return None
        if body.type != 'statement_block':
            return body
        ret = next(JsSyntax.walk(body, {'return_statement'}), None)
        return ret.named_children[0] if ret is not None and ret.named_children else None

    @classmethod
    def enclosing(cls, node):
        """(nearest named function, enclosing class name); anonymous callbacks are skipped."""
        function = ''
        n = node.parent
        while n is not None and not function:
            if n.type in cls.FUNCTIONS:
                function = cls.name(n)
            n = n.parent
        owner = JsSyntax.ancestor(node, cls.CLASSES)
        name = owner.child_by_field_name('name') if owner is not None else None
        return function, JsSyntax.text(name)

    @classmethod
    def named_ancestor(cls, node):
        """The nearest enclosing function that has a name (`useMemo(() => new Client())` inside a hook is skipped)."""
        fn = JsSyntax.ancestor(node, cls.FUNCTIONS)
        while fn is not None and not cls.name(fn):
            fn = JsSyntax.ancestor(fn, cls.FUNCTIONS)
        return fn

    @staticmethod
    def returns(fn):
        """The function returns something: an arrow function's expression body or a `return` statement."""
        body = fn.child_by_field_name('body')
        return body is not None and (body.type != 'statement_block' or any(JsSyntax.walk(body, {'return_statement'})))
