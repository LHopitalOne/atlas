"""DjangoSettings: what `settings.NAME` is bound to in a repository's settings modules."""

from ..syntax import PythonSyntax


class DjangoSettings:
    """Module-level assignments in settings modules (a `settings` or `envs` package, or `settings.py`), read on first
    use. When several modules set a name, base settings win over environment ones (devstack, local) and those over
    test settings; within one module the last assignment wins. A settings module's `from module import *` brings in
    that module's assignments (and its own star imports) where the statement stands, at the importer's rank."""

    PACKAGES = frozenset({'settings', 'envs', 'conf', 'config'})
    BASE = frozenset({'base', 'common', 'defaults', 'production', 'prod', 'settings'})
    TEST_WORD = 'test'
    BASE_RANK, OTHER_RANK, TEST_RANK = 0, 1, 2
    MAX_STARS = 5  # star imports followed in a chain

    def __init__(self, sources, names=None):
        self._sources = sources
        self._names = names  # NameLookup, to follow star imports (None: not followed)
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
            for name, where, node in self._assignments(source, (source.path,)):
                known = values.get(name)
                if known is None or rank <= known[0]:
                    values[name] = (rank, where, node)
        return values

    @classmethod
    def _rank(cls, module):
        if cls.TEST_WORD in module:
            return cls.TEST_RANK
        return cls.BASE_RANK if module in cls.BASE else cls.OTHER_RANK

    def _assignments(self, source, chain):
        """(name, file, value node) of a module's assignments in order, star imports read where they stand."""
        for st in PythonSyntax.module_statements(source.root):
            if st.type == 'import_from_statement':
                yield from self._starred(source, st, chain)
            for e in st.named_children if st.type == 'expression_statement' else ():
                if e.type == 'assignment' and e.child_by_field_name('left').type == 'identifier':
                    yield PythonSyntax.text(e.child_by_field_name('left')), source, e.child_by_field_name('right')

    def _starred(self, source, statement, chain):
        ref = self._names.table(source).star_import(statement) if self._names is not None else None
        target = self._names.locate(ref) if ref is not None else None
        if target is not None and target.path not in chain and len(chain) <= self.MAX_STARS:
            yield from self._assignments(target, (*chain, target.path))
