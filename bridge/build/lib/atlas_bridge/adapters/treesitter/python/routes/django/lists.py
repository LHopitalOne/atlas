"""Module-level URL lists: what `urlpatterns = [...]`, `+=`, `.append()`, `.extend()` and `.insert()` put in them."""

from typing import NamedTuple

from ...syntax import PythonSyntax


class Contribution(NamedTuple):
    """One addition to a list: a whole list expression ('expr') or a single item ('item')."""

    kind: str
    node: object


class UrlLists:
    """Per file, read once: {list name: [Contribution]} from module-level statements, in order. A reassignment that
    does not read the list replaces what it had; one that does (`urlpatterns = urlpatterns + [...]`) adds to it."""

    EXPR, ITEM = 'expr', 'item'

    def __init__(self):
        self._cache = {}  # path -> {name: [Contribution]}

    def lists_in(self, source):
        """{list name: [Contribution]} of a file's module-level lists."""
        found = self._cache.get(source.path)
        if found is None:
            found = self._cache[source.path] = self._read(source)
        return found

    @classmethod
    def _read(cls, source):
        out = {}
        for st in PythonSyntax.module_statements(source.root):
            if st.type != 'expression_statement':
                continue
            for e in st.named_children:
                if e.type == 'assignment':
                    cls._assignment(out, e)
                elif e.type == 'augmented_assignment' and PythonSyntax.text(e.child_by_field_name('operator')) == '+=':
                    left = e.child_by_field_name('left')
                    if left.type == 'identifier':
                        out.setdefault(PythonSyntax.text(left), []).append(cls._expr(e.child_by_field_name('right')))
                elif e.type == 'call':
                    cls._method_call(out, e)
        return out

    @classmethod
    def _expr(cls, node):
        return Contribution(cls.EXPR, node)

    @classmethod
    def _assignment(cls, out, e):
        left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
        if left.type == 'identifier' and right is not None:
            name = PythonSyntax.text(left)
            if name in PythonSyntax.identifiers(right):  # urlpatterns = urlpatterns + [...]: keeps what it had
                out.setdefault(name, []).append(cls._expr(right))
            else:
                out[name] = [cls._expr(right)]

    @classmethod
    def _method_call(cls, out, e):
        fn = e.child_by_field_name('function')
        if fn.type != 'attribute' or fn.child_by_field_name('object').type != 'identifier':
            return
        pos, _ = PythonSyntax.call_args(e)
        owner = PythonSyntax.text(fn.child_by_field_name('object'))
        attr = PythonSyntax.text(fn.child_by_field_name('attribute'))
        if attr == 'append' and pos:
            out.setdefault(owner, []).append(Contribution(cls.ITEM, pos[0]))
        elif attr == 'extend' and pos:
            out.setdefault(owner, []).append(cls._expr(pos[0]))
        elif attr == 'insert' and len(pos) > 1:
            out.setdefault(owner, []).append(Contribution(cls.ITEM, pos[1]))
