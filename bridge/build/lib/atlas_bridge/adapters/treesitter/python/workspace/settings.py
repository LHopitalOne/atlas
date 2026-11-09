"""DjangoSettings: what `settings.NAME` is bound to in a repository's settings modules."""

from ..syntax import PythonSyntax


class DjangoSettings:
    """Module-level assignments in settings modules (a `settings` or `envs` package, or `settings.py`), read on first
    use. When several modules set a name, base settings win over environment ones (devstack, local) and those over
    test settings; within one module the last assignment wins."""

    PACKAGES = frozenset({'settings', 'envs', 'conf', 'config'})
    BASE = frozenset({'base', 'common', 'defaults', 'production', 'prod', 'settings'})
    TEST_WORD = 'test'
    BASE_RANK, OTHER_RANK, TEST_RANK = 0, 1, 2

    def __init__(self, sources):
        self._sources = sources
        self._values = None  # name -> (rank, source, value node)

    def value(self, name):
        """(source, value node) of the setting `name`, or None."""
        if self._values is None:
            self._values = self._read()
        found = self._values.get(name)
        return found[1:] if found else None

    def _read(self):
        values = {}
        for source in self._sources:
            parts = source.path.split('/')
            module = parts[-1].removesuffix('.py')
            if source.test or not (self.PACKAGES & set(parts[:-1]) or module == 'settings'):
                continue
            rank = self._rank(module)
            for name, node in self._assignments(source):
                known = values.get(name)
                if known is None or rank <= known[0]:
                    values[name] = (rank, source, node)
        return values

    @classmethod
    def _rank(cls, module):
        if cls.TEST_WORD in module:
            return cls.TEST_RANK
        return cls.BASE_RANK if module in cls.BASE else cls.OTHER_RANK

    @staticmethod
    def _assignments(source):
        for st in PythonSyntax.module_statements(source.root):
            for e in st.named_children if st.type == 'expression_statement' else ():
                if e.type == 'assignment' and e.child_by_field_name('left').type == 'identifier':
                    yield PythonSyntax.text(e.child_by_field_name('left')), e.child_by_field_name('right')
