"""Members of TypeScript enums: `QueueName.Mail` is the initializer of `Mail` in `enum QueueName { Mail = 'mail' }`."""

from ..syntax.nodes import JsSyntax


class EnumMembers:
    """The member initializers of the enums one file (a ChannelFile) declares or imports. A member without an
    initializer (a number the compiler counts) is not read."""

    DECLARATION = 'enum_declaration'
    EXPORT = 'export_statement'

    def __init__(self, file):
        self._file = file

    def member(self, obj, key):
        """(file, initializer) of `obj.key` when `obj` names an enum, else None."""
        obj = JsSyntax.unwrap(obj)
        if obj is None or obj.type != 'identifier':
            return None
        found = self._declared(JsSyntax.text(obj))
        if found is None:
            imported = self._file.imported(obj)
            found = imported if imported is not None and imported[1].type == self.DECLARATION else None
        if found is None:
            return None
        file, enum = found
        body = enum.child_by_field_name('body')
        for m in body.named_children if body is not None else ():
            name = m.child_by_field_name('name') if m.type == 'enum_assignment' else None
            text = (
                (JsSyntax.string(name) if name.type == 'string' else JsSyntax.text(name)) if name is not None else None
            )
            if text == key:
                return file, m.child_by_field_name('value')
        return None

    def _declared(self, name):
        """(this file, enum declaration) of a top-level enum by this name, or None."""
        for child in self._file.module.source.root.named_children:
            node = child.child_by_field_name('declaration') if child.type == self.EXPORT else child
            if (
                node is not None
                and node.type == self.DECLARATION
                and JsSyntax.text(node.child_by_field_name('name')) == name
            ):
                return self._file, node
        return None
