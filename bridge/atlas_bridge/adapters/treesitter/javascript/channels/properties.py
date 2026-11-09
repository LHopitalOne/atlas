"""Constructor parameter properties: `constructor(private readonly queue: Queue)` declares `this.queue`."""

from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax


class ParameterProperties:
    """The constructor parameter that declares a field of the class around a node."""

    MODIFIERS = frozenset({'accessibility_modifier', 'readonly', 'override_modifier'})
    CONSTRUCTOR = 'constructor'

    @classmethod
    def of(cls, node, key):
        """The parameter that declares `this.key` in the constructor of the class around `node`, or None."""
        owner = JsSyntax.ancestor(node, Functions.CLASSES)
        body = owner.child_by_field_name('body') if owner is not None else None
        for method in body.named_children if body is not None else ():
            if (
                method.type != 'method_definition'
                or JsSyntax.text(method.child_by_field_name('name')) != cls.CONSTRUCTOR
            ):
                continue
            for param in method.child_by_field_name('parameters').named_children:
                pattern = param.child_by_field_name('pattern')
                declares = any(c.type in cls.MODIFIERS for c in param.children)
                if declares and pattern is not None and JsSyntax.text(pattern) == key:
                    return param
        return None

    @staticmethod
    def decorators(param):
        """The calls of the decorators on a parameter: `@InjectQueue('mail')`."""
        found = (d.named_children[0] for d in param.children if d.type == 'decorator' and d.named_children)
        return [c for c in found if c.type == 'call_expression']
