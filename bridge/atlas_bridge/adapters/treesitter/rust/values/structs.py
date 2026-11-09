"""The crate's structs: the type each field is declared with and the values struct expressions give it."""

from ..names import ItemPath
from ..syntax import RustSyntax
from .functions import CrateFunctions


class CrateStructs:
    """Structs by name. A field's values are what every `Name { field: value }` (or `Self { field }` in an impl of
    Name, or the shorthand `Name { field }`) sets it to: what its constructors store."""

    def __init__(self, workspace):
        self._workspace = workspace
        self._fields = None  # (struct name, field) -> [(file, type node)]
        self._inits = None  # (struct name, field) -> [(file, value node)]

    def field_type(self, struct, field):
        """The type a struct's field is declared with, as (file, type node), or None."""
        found = self._index()[0].get((struct, field), [])
        return found[0] if len(found) == 1 else None

    def initializers(self, struct, field) -> list:
        """(file, value node) of every value a struct expression gives the field."""
        return self._index()[1].get((struct, field), [])

    def _index(self):
        if self._fields is None:
            self._fields, self._inits = {}, {}
            for f in self._workspace.files:
                for s in f.nodes('struct'):
                    self._declared(f, s)
                for e in f.nodes('init'):
                    self._initialized(f, e)
        return self._fields, self._inits

    def _declared(self, file, struct):
        body = struct.child_by_field_name('body')
        name = RustSyntax.name(struct)
        for d in body.named_children if body is not None else ():
            if d.type == 'field_declaration':
                key = (name, RustSyntax.text(d.child_by_field_name('name')))
                self._fields.setdefault(key, []).append((file, d.child_by_field_name('type')))

    def _initialized(self, file, expr):
        name = ItemPath.last(expr.child_by_field_name('name'))
        if name == 'Self':
            name = CrateFunctions.impl_type(expr)
        body = expr.child_by_field_name('body')
        for i in body.named_children if body is not None else ():
            if i.type == 'field_initializer':
                field, value = i.child_by_field_name('field'), i.child_by_field_name('value')
            elif i.type == 'shorthand_field_initializer' and i.named_children:
                field = value = i.named_children[0]
            else:
                continue
            self._inits.setdefault((name, RustSyntax.text(field)), []).append((file, value))
