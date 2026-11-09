"""Whether a call sends an HTTP request, as a SCIP index sees it: the library function it really reaches."""

import re

from ..syntax import PythonSyntax


class Senders:
    """With an index, a call is a request when its name resolves into an HTTP client library, and is not one when it
    resolves into any other library (dict.get, Django's test client). A call into the repository's own code, or one
    the index knows nothing of, is left to syntax: own wrappers are often pass-throughs the URL cannot be followed
    through."""

    LIBRARY = re.compile(r'^`(?:requests|httpx|aiohttp|urllib3|urllib\.request|http\.client)[.`]')  # their modules

    def __init__(self, workspace):
        self._workspace = workspace

    def verdict(self, source, call, name) -> bool | None:
        """True: an HTTP library sends it; False: another library's function; None: own code, or not known."""
        graph = self._workspace.graph
        if graph is None:
            return None
        fn = call.child_by_field_name('function')
        node = fn.child_by_field_name('attribute') if fn.type == 'attribute' else fn
        targets = graph.resolves(self._workspace.repo, source.path, PythonSyntax.line(node), name)
        if not targets:
            return None
        if any(self.LIBRARY.match(t.key) for t in targets):
            return True
        if any(t.local for t in targets):
            return None  # the repository's own wrapper, often a pass-through (*args, **kwargs): syntax decides
        return False
