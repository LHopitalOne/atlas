"""What a file exports: the expression each exported name is bound to."""

from ..syntax.nodes import JsSyntax


class ModuleExports:
    """name -> the expression a file exports under it: `export const name = value`, `export { local as name }`,
    `export default value`, `module.exports = { name: value, local }` and `exports.name = value`. A name exported
    from another module (`export { name } from './x'`) is not followed."""

    DEFAULT = 'default'
    MODULE_EXPORTS = 'module.exports'
    EXPORTS = 'exports.'
    NAMED_DECLARATIONS = frozenset(
        {'function_declaration', 'generator_function_declaration', 'class_declaration', 'abstract_class_declaration'}
    )

    def __init__(self, source):
        self._source = source
        self._names = None

    def value(self, name):
        """The expression exported as `name` ('default' for the default export), or None. A function or class
        declaration stands for itself."""
        return self._table().get(name)

    def names(self) -> dict:
        """{exported name: its expression or declaration}."""
        return dict(self._table())

    def _table(self):
        if self._names is None:
            self._names, self._locals, self._aliases = {}, {}, []
            for child in self._source.root.named_children:
                self._statement(child)
            for exported, local in self._aliases:
                if local in self._locals:
                    self._names.setdefault(exported, self._locals[local])
        return self._names

    def _statement(self, node):
        if node.type in JsSyntax.DECLARATIONS:
            self._declare(node, self._locals)
        elif node.type == 'expression_statement':
            self._commonjs(node)
        elif node.child_by_field_name('name') is not None and node.type in self.NAMED_DECLARATIONS:
            self._locals.setdefault(JsSyntax.text(node.child_by_field_name('name')), node)
        elif node.type == 'export_statement' and node.child_by_field_name('source') is None:
            self._export(node)

    def _export(self, node):
        declaration = node.child_by_field_name('declaration')
        if declaration is not None and declaration.type in JsSyntax.DECLARATIONS:
            self._declare(declaration, self._locals)
            self._declare(declaration, self._names)
        elif declaration is not None:
            self._statement(declaration)
            name = declaration.child_by_field_name('name')
            if name is not None:
                self._names.setdefault(JsSyntax.text(name), declaration)
        value = declaration if any(c.type == self.DEFAULT for c in node.children) else None
        value = node.child_by_field_name('value') or value
        if value is not None:
            self._names[self.DEFAULT] = value
        for clause in (c for c in node.named_children if c.type == 'export_clause'):
            for spec in clause.named_children:
                name, alias = spec.child_by_field_name('name'), spec.child_by_field_name('alias')
                if name is not None:
                    self._aliases.append((JsSyntax.text(alias or name), JsSyntax.text(name)))

    @staticmethod
    def _declare(declaration, table):
        for d in declaration.named_children:
            name, value = d.child_by_field_name('name'), d.child_by_field_name('value')
            if name is not None and value is not None and name.type == 'identifier':
                table.setdefault(JsSyntax.text(name), value)

    def _commonjs(self, statement):
        e = statement.named_children[0] if statement.named_children else None
        if e is None or e.type != 'assignment_expression':
            return
        left, right = JsSyntax.text(e.child_by_field_name('left')), e.child_by_field_name('right')
        if left == self.MODULE_EXPORTS:
            self._names.setdefault(self.DEFAULT, right)
            self._members(JsSyntax.unwrap(right))
        elif left.startswith(self.EXPORTS) and left.count('.') == 1:
            self._names.setdefault(left[len(self.EXPORTS) :], right)

    def _members(self, obj):
        """The properties of `module.exports = { ... }`, each exported under its key."""
        if obj is None or obj.type != 'object':
            return
        for p in obj.named_children:
            if p.type == 'pair':
                key = p.child_by_field_name('key')
                name = JsSyntax.string(key) if key.type == 'string' else JsSyntax.text(key)
                self._names.setdefault(name, p.child_by_field_name('value'))
            elif p.type == 'shorthand_property_identifier':
                self._aliases.append((JsSyntax.text(p), JsSyntax.text(p)))
