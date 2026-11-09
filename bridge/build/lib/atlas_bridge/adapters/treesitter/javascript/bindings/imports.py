"""What a file imports and what it exports by default."""

from ..syntax.nodes import JsSyntax


class ImportTable:
    """name -> (module source, imported name or 'default') for `import` statements and `x = require('...')`."""

    DEFAULT = 'default'

    def __init__(self, source):
        self._source = source
        self._names = None

    def get(self, name):
        """(module source, imported name or 'default') for an imported name, or None."""
        return self._table().get(name)

    def exported_name(self, name):
        """The name a module exports `name` under: the imported name, or `name` itself for a default import."""
        imported = self.get(name)
        if imported is None:
            return None
        return name if imported[1] == self.DEFAULT else imported[1]

    def default_export(self):
        """The name `export default name` or `module.exports = name` exports, or None."""
        for child in self._source.root.named_children:
            if child.type == 'export_statement':
                value = child.child_by_field_name('value')
                if value is not None and value.type == 'identifier':
                    return JsSyntax.text(value)
            elif child.type == 'expression_statement':
                name = self._module_exports(child)
                if name is not None:
                    return name
        return None

    @staticmethod
    def _module_exports(statement):
        e = statement.named_children[0] if statement.named_children else None
        if e is not None and e.type == 'assignment_expression':
            left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
            if JsSyntax.text(left) == 'module.exports' and right.type == 'identifier':
                return JsSyntax.text(right)
        return None

    def _table(self):
        if self._names is None:
            self._names = {}
            for child in self._source.root.named_children:
                if child.type == 'import_statement':
                    self._import_statement(child)
                elif child.type in JsSyntax.DECLARATIONS:
                    self._requires(child)
        return self._names

    def _requires(self, declaration):
        for d in declaration.named_children:
            name, value = d.child_by_field_name('name'), d.child_by_field_name('value')
            source = JsSyntax.require(value)
            if name is not None and name.type == 'identifier' and source:
                self._names[JsSyntax.text(name)] = (source, self.DEFAULT)

    def _import_statement(self, node):
        source = node.child_by_field_name('source')
        clause = next((c for c in node.named_children if c.type == 'import_clause'), None)
        if source is None or clause is None:
            return
        src = JsSyntax.string(source)
        for c in clause.named_children:
            if c.type == 'identifier':
                self._names[JsSyntax.text(c)] = (src, self.DEFAULT)
            elif c.type == 'named_imports':
                for spec in c.named_children:
                    name, alias = spec.child_by_field_name('name'), spec.child_by_field_name('alias')
                    if name is not None:
                        self._names[JsSyntax.text(alias or name)] = (src, JsSyntax.text(name))
