"""Words that may name the service a reverse() URL is handed to."""

from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Value


class PayloadHints:
    """The module docstring, the identifiers and strings of the enclosing function (not its docstring, which talks
    about other code), and the qualified names and files of the production functions that call it, two levels up.
    The callers' own local words are left out: they name services by accident (SAML's RelayState)."""

    WORDS = ('identifier', 'string_content')

    def __init__(self, workspace):
        self._workspace = workspace
        self._words = {}  # (path, function start byte) -> words of that function

    def hints_for(self, scope):
        hints = set()
        doc = PythonSyntax.docstring(scope.source.root)
        if doc is not None:
            hints.add(PythonSyntax.text(doc))
        if scope.func is None:
            return hints
        hints |= self.words(scope.source, scope.func)
        for source, call in self._production_callers(scope.source, scope.func):
            outer = Scope.at(source, call)
            hints |= {source.path, outer.qualified}
            if outer.func is None:
                continue
            for source2, call2 in self._production_callers(source, outer.func):
                hints |= {source2.path, Scope.at(source2, call2).qualified}
        return hints

    def _production_callers(self, source, func):
        return [
            (g, c) for g, c in self._workspace.callers.callers_of(source, func) if not self._workspace.is_test(g, c)
        ]

    def words(self, source, func):
        """Identifiers and string contents of a function, outside its docstring."""
        key = (source.path, func.start_byte)
        found = self._words.get(key)
        if found is None:
            doc = PythonSyntax.docstring(func.child_by_field_name('body'))
            skip = (doc.start_byte, doc.end_byte) if doc is not None else (0, 0)
            nodes = PythonSyntax.walk(func, self.WORDS)
            found = frozenset(Value.hint(PythonSyntax.text(n)) for n in nodes if not skip[0] <= n.start_byte < skip[1])
            self._words[key] = found
        return found
