"""Module-level URL lists: what `urlpatterns = [...]`, `+=`, `.append()`, `.extend()` and `.insert()` put in them,
also inside module-level `for` loops."""

from typing import NamedTuple

from ...syntax import PythonSyntax


class Contribution(NamedTuple):
    """One addition to a list: a whole list expression ('expr') or a single item ('item'), and the module-level
    `for` statement it is made in (or None)."""

    kind: str
    node: object
    loop: object = None


class UrlLists:
    """Per file, read once: {list name: [Contribution]} from module-level statements, in order. A reassignment that
    does not read the list replaces what it had; one that does (`urlpatterns = urlpatterns + [...]`) adds to it.
    A statement in the body of a module-level `for name in ...:` loop is a contribution made under that loop."""

    EXPR, ITEM = 'expr', 'item'
    LOOP = 'for_statement'

    def __init__(self):
        self._cache = {}  # path -> {name: [Contribution]}

    def lists_in(self, source):
        """{list name: [Contribution]} of a file's module-level lists."""
        found = self._cache.get(source.path)
        if found is None:
            found = self._cache[source.path] = {}
            self._statements(found, PythonSyntax.module_statements(source.root), None)
        return found

    @classmethod
    def _statements(cls, out, statements, loop):
        for st in statements:
            if st.type == cls.LOOP and loop is None:
                body = st.child_by_field_name('body')
                if body is not None:
                    cls._statements(out, PythonSyntax.module_statements(body), st)
            elif st.type == 'expression_statement':
                for e in st.named_children:
                    cls._expression(out, e, loop)

    @classmethod
    def _expression(cls, out, e, loop):
        if e.type == 'assignment':
            cls._assignment(out, e, loop)
        elif e.type == 'augmented_assignment' and PythonSyntax.text(e.child_by_field_name('operator')) == '+=':
            left = e.child_by_field_name('left')
            if left.type == 'identifier':
                out.setdefault(PythonSyntax.text(left), []).append(cls._expr(e.child_by_field_name('right'), loop))
        elif e.type == 'call':
            cls._method_call(out, e, loop)

    @classmethod
    def _expr(cls, node, loop):
        return Contribution(cls.EXPR, node, loop)

    @classmethod
    def _assignment(cls, out, e, loop):
        left, right = e.child_by_field_name('left'), e.child_by_field_name('right')
        if left.type == 'identifier' and right is not None:
            name = PythonSyntax.text(left)
            if name in PythonSyntax.identifiers(right):  # urlpatterns = urlpatterns + [...]: keeps what it had
                out.setdefault(name, []).append(cls._expr(right, loop))
            elif loop is None:
                out[name] = [cls._expr(right, loop)]

    @classmethod
    def _method_call(cls, out, e, loop):
        fn = e.child_by_field_name('function')
        if fn.type != 'attribute' or fn.child_by_field_name('object').type != 'identifier':
            return
        pos, _ = PythonSyntax.call_args(e)
        owner = PythonSyntax.text(fn.child_by_field_name('object'))
        attr = PythonSyntax.text(fn.child_by_field_name('attribute'))
        if attr == 'append' and pos:
            out.setdefault(owner, []).append(Contribution(cls.ITEM, pos[0], loop))
        elif attr == 'extend' and pos:
            out.setdefault(owner, []).append(cls._expr(pos[0], loop))
        elif attr == 'insert' and len(pos) > 1:
            out.setdefault(owner, []).append(Contribution(cls.ITEM, pos[1], loop))
