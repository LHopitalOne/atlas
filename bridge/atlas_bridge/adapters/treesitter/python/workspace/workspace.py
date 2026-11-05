"""PythonWorkspace: a repository's Python files with the indexes every collector shares."""

from ...kit import TestPathPolicy, Workspace
from ..syntax import PythonSyntax
from .callers import CallerIndex
from .locals import ClassAttributes, LocalIndex
from .modules import ModuleIndex
from .names import NameLookup


class PythonWorkspace(Workspace):
    """Reads each file once with one query, and indexes modules, functions, classes and the calls collectors want.

    Collectors reach the shared lookups through `names` (module-level names and imports), `locals` (assignments in
    functions), `attributes` (class and self attributes) and `callers` (who calls a function).
    """

    QUERY = """
    (call function: [(identifier) @fn (attribute attribute: (identifier) @fn)]
      (#any-of? @fn "urlopen" "request" "get" "post" "put" "patch" "delete" "head" "options" "reverse" "reverse_lazy"
       "register_blueprint" "include_router" "add_url_rule")) @call
    (decorated_definition) @dec
    (function_definition name: (identifier) @defname) @def
    (class_definition name: (identifier) @clsname) @cls
    """

    def index(self):
        self._calls = []  # (source, call node, called name) of the names in QUERY, in file order
        self._decorated = []  # (source, decorated_definition node)
        self._functions = {}  # function name -> [(source, node)]
        self._classes = {}  # class name -> [(source, node)]
        for source in self.sources:
            self._read(source)
        # Module ranking deliberately uses the kit's path rule, not PythonTestPolicy: a module under scripts/ or
        # .github/ ranks as production code here, as it did in the legacy ranking.
        self.names = NameLookup(ModuleIndex(self.sources, TestPathPolicy()))
        self.locals = LocalIndex()
        self.attributes = ClassAttributes()
        self.callers = CallerIndex(self.sources, self._functions)

    def _read(self, source):
        caps = source.captures(self.QUERY)
        self._calls += [(source, c, PythonSyntax.callee(c)) for c in caps.get('call', ())]
        self._decorated += [(source, d) for d in caps.get('dec', ())]
        for d in caps.get('def', ()):
            self._functions.setdefault(PythonSyntax.name(d), []).append((source, d))
        for c in caps.get('cls', ()):
            self._classes.setdefault(PythonSyntax.name(c), []).append((source, c))

    def calls(self, names):
        """[(source, call node, name)] of the calls to any of `names` (from QUERY's list), in file order."""
        return [found for found in self._calls if found[2] in names]

    def decorated(self):
        """[(source, decorated_definition node)] across the repository."""
        return list(self._decorated)

    def classes(self, name):
        """[(source, class_definition node)] of every class with this name."""
        return self._classes.get(name, [])

    def is_test(self, source, node=None) -> bool:
        """Test code by path, or inside a `test_*` / `test` function or a `Test*` class."""
        if source.test:
            return True
        n = node.parent if node is not None else None
        while n is not None:
            if n.type in PythonSyntax.FUNCTION and self._is_test_name(PythonSyntax.name(n)):
                return True
            if n.type in PythonSyntax.CLASS and PythonSyntax.name(n).startswith('Test'):
                return True
            n = n.parent
        return False

    @staticmethod
    def _is_test_name(name):
        return name.startswith('test_') or name == 'test'
