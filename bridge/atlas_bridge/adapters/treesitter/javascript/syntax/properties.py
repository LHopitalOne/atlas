"""Constructor parameter properties: `constructor(private readonly queue: Queue)` declares `this.queue`; and the
constructor parameter a field is set from (`this.url = url`)."""

from .functions import Functions
from .nodes import JsSyntax


class ParameterProperties:
    """The constructor parameter that declares a field of the class around a node."""

    MODIFIERS = frozenset({'accessibility_modifier', 'readonly', 'override_modifier'})
    CONSTRUCTOR = 'constructor'

    @classmethod
    def of(cls, node, key):
        """The parameter that declares `this.key` in the constructor of the class around `node`, or None."""
        ctor = cls.constructor(node)
        for param in ctor.child_by_field_name('parameters').named_children if ctor is not None else ():
            pattern = param.child_by_field_name('pattern')
            declares = any(c.type in cls.MODIFIERS for c in param.children)
            if declares and pattern is not None and JsSyntax.text(pattern) == key:
                return param
        return None

    @classmethod
    def constructor(cls, node):
        """The constructor of the class around `node`, or None."""
        owner = JsSyntax.ancestor(node, Functions.CLASSES)
        body = owner.child_by_field_name('body') if owner is not None else None
        for method in body.named_children if body is not None else ():
            if (
                method.type == 'method_definition'
                and JsSyntax.text(method.child_by_field_name('name')) == cls.CONSTRUCTOR
            ):
                return method
        return None

    @classmethod
    def source_param(cls, node, key):
        """The name of the constructor parameter `this.key` holds: a parameter property, or a parameter the
        constructor assigns to it as it is (`this.url = url`); '' when it holds anything else."""
        if cls.of(node, key) is not None:
            return key
        ctor = cls.constructor(node)
        if ctor is None:
            return ''
        params = {n for p in ctor.child_by_field_name('parameters').named_children for n in cls._names(p)}
        for assigned in JsSyntax.walk(ctor.child_by_field_name('body'), {'assignment_expression'}):
            right = JsSyntax.unwrap(assigned.child_by_field_name('right'))
            if JsSyntax.text(assigned.child_by_field_name('left')) == f'this.{key}' and right.type == 'identifier':
                return JsSyntax.text(right) if JsSyntax.text(right) in params else ''
        return ''

    @staticmethod
    def _names(param):
        pattern = param.child_by_field_name('pattern') if param.type in JsSyntax.PARAMETERS else param
        return [JsSyntax.text(pattern)] if pattern is not None and pattern.type == 'identifier' else []

    @staticmethod
    def decorators(param):
        """The calls of the decorators on a parameter: `@InjectQueue('mail')`."""
        found = (d.named_children[0] for d in param.children if d.type == 'decorator' and d.named_children)
        return [c for c in found if c.type == 'call_expression']
