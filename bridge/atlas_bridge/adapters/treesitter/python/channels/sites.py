"""The call sites that supply a function's parameters: its callers, or for `__init__` the calls of its class."""

from ..calls import CallSite
from ..syntax import PythonSyntax


class FunctionSites:
    """Where a function is called, with the argument each parameter gets there."""

    INIT = '__init__'
    MAX_SITES = 8  # call sites followed per function

    def __init__(self, workspace):
        self._workspace = workspace

    @staticmethod
    def params(func):
        """[(name, default)] a caller supplies: a method's `self` or `cls` is left out."""
        params = PythonSyntax.params(func)
        if PythonSyntax.is_method(func) and params and params[0][0] in PythonSyntax.SELF_NAMES:
            return params[1:]
        return params

    def of(self, scope) -> list[CallSite]:
        """The call sites of the function around `scope` (without `*args` at the call), at most MAX_SITES. Sites in
        test code supply a function outside it nothing: a test picks its own topics and ports, not the service's."""
        func = scope.func
        if func is None:
            return []
        if PythonSyntax.name(func) == self.INIT and scope.cls is not None:
            found = self._constructions(scope.source, scope.cls)
        else:
            found = self._workspace.callers.callers_of(scope.source, func)
        if not self._workspace.is_test(scope.source, func):
            found = [(source, call) for source, call in found if not self._workspace.is_test(source, call)]
        params = self.params(func)
        sites = [CallSite.at(source, call, params) for source, call in found]
        return [s for s in sites if not s.splat][: self.MAX_SITES]

    def _constructions(self, source, cls):
        name = PythonSyntax.name(cls)
        unique = len([c for c in self._workspace.classes(name) if not c[0].test]) == 1
        return self._workspace.callers.constructions_of(source, cls, unique)
