"""Members of classes and object literals, and the types members and parameters are annotated with."""

from .functions import Functions
from .nodes import JsSyntax


class Members:
    CONTAINERS = Functions.CLASSES | {'object'}  # what `this` can stand for

    @classmethod
    def of_this(cls, node, field):
        """What `this.field` is set to, from the nearest enclosing class or object literal that sets it."""
        container = JsSyntax.ancestor(node, cls.CONTAINERS)
        while container is not None:
            found = cls.field_values(container, field)
            if found:
                return found
            container = JsSyntax.ancestor(container, cls.CONTAINERS)
        return []

    @classmethod
    def field_values(cls, container, field):
        """Initializers of `field`: a class field (`field = ...`), an object key (`field: ...`), `this.field = ...`."""
        if container.type == 'object':
            body, members = container, [p for p in container.named_children if p.type == 'pair']
        else:
            body = container.child_by_field_name('body')
            if body is None:
                return []
            members = [m for m in body.named_children if m.type in Functions.FIELDS]
        out = []
        for m in members:
            name = m.child_by_field_name('name') or m.child_by_field_name('property') or m.child_by_field_name('key')
            value = m.child_by_field_name('value')
            if value is not None and JsSyntax.text(name) == field:
                out.append(value)
        for n in JsSyntax.walk(body, {'assignment_expression'}):
            if JsSyntax.text(n.child_by_field_name('left')) == 'this.' + field:
                out.append(n.child_by_field_name('right'))
        return out

    @staticmethod
    def first_type(node):
        """The first type name in a type annotation: `: Client` -> 'Client'."""
        for n in JsSyntax.walk(node, {'type_identifier'}) if node is not None else ():
            return JsSyntax.text(n)
        return ''

    @classmethod
    def param_type(cls, param, name):
        """The type of `name` in a parameter: `api: Client`, or `{api}: {api: Client}` for a destructured one."""
        if param.type not in JsSyntax.PARAMETERS:
            return ''
        pattern, annotation = param.child_by_field_name('pattern'), param.child_by_field_name('type')
        if pattern is not None and pattern.type == 'identifier':
            return cls.first_type(annotation)
        for n in JsSyntax.walk(annotation, {'property_signature'}) if annotation is not None else ():
            if JsSyntax.text(n.child_by_field_name('name')) == name:
                return cls.first_type(n.child_by_field_name('type'))
        return ''

    @classmethod
    def declared_types(cls, root):
        """{name: type} for typed members of a file's interfaces, object types and classes (`api: Client`)."""
        types = {}
        for n in JsSyntax.walk(root, {'property_signature', 'public_field_definition'}):
            name = JsSyntax.text(n.child_by_field_name('name'))
            types.setdefault(name, cls.first_type(n.child_by_field_name('type')))
        return types
