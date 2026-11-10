"""Names bound inside functions and classes: local assignments, class attributes and `self.attr = ...`."""

from typing import NamedTuple

from ..syntax import PythonSyntax


class LocalAssignment(NamedTuple):
    """One binding of a local name: where it ends, the value, and whether it is `name += value`."""

    end: int
    value: object
    augmented: bool


class LocalIndex:
    """The local assignments of each function, read once per function."""

    def __init__(self):
        self._cache = {}  # (path, function start byte) -> {name: [LocalAssignment]}

    def assignments_in(self, source, func):
        """{name: [LocalAssignment]} of a function body, in source order (nested scopes left out)."""
        key = (source.path, func.start_byte)
        found = self._cache.get(key)
        if found is None:
            found = self._cache[key] = self._read(func)
        return found

    def before(self, source, func, name, byte):
        """The assignments of `name` in `func` that end at or before `byte`."""
        return [a for a in self.assignments_in(source, func).get(name, []) if a.end <= byte]

    @staticmethod
    def _read(func):
        found = {}
        text = PythonSyntax.text
        for n in PythonSyntax.body_nodes(func.child_by_field_name('body')):
            if n.type == 'assignment':
                for name, v in PythonSyntax.assignment_targets(n):
                    found.setdefault(name, []).append(LocalAssignment(n.end_byte, v, False))
            elif n.type == 'augmented_assignment' and text(n.child_by_field_name('operator')) == '+=':
                left = n.child_by_field_name('left')
                if left.type == 'identifier':
                    found.setdefault(text(left), []).append(
                        LocalAssignment(n.end_byte, n.child_by_field_name('right'), True)
                    )
            elif n.type == 'named_expression':
                value = n.child_by_field_name('value')
                found.setdefault(PythonSyntax.name(n), []).append(LocalAssignment(n.end_byte, value, False))
        for v in found.values():
            v.sort(key=lambda a: a.end)
        return found


class ClassAttributes:
    """Per class, read once: class-level assignments and the first `self.attr = ...` of each attribute."""

    def __init__(self):
        self._cache = {}  # (path, class start byte) -> (class attributes, instance attributes)

    def own(self, source, cls):
        """{name: value} of the class body's own assignments."""
        return self._of(source, cls)[0]

    def attribute(self, source, cls, attr):
        """What `self.attr` was assigned: a class attribute, else the first `self.attr = ...` in the class."""
        own, inst = self._of(source, cls)
        return own[attr] if attr in own else inst.get(attr)

    def _of(self, source, cls):
        key = (source.path, cls.start_byte)
        found = self._cache.get(key)
        if found is None:
            found = self._cache[key] = self._read(cls)
        return found

    @classmethod
    def _read(cls, klass):
        own, inst = {}, {}
        text = PythonSyntax.text
        body = klass.child_by_field_name('body')
        for st in body.named_children if body is not None else ():
            if st.type == 'expression_statement':
                for a in st.named_children:
                    if a.type == 'assignment':
                        for n, v in PythonSyntax.assignment_targets(a):
                            own.setdefault(n, v)
        for n in PythonSyntax.walk(body, ('assignment',)) if body is not None else ():
            left = n.child_by_field_name('left')
            if left.type == 'attribute' and PythonSyntax.is_self(left.child_by_field_name('object')):
                inst.setdefault(text(left.child_by_field_name('attribute')), n.child_by_field_name('right'))
        return own, inst
