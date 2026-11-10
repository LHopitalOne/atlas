"""RequestCalls: HTTP requests sent with requests/httpx/aiohttp/urllib3/urllib-style clients."""

from .....core.http import ANY, Extraction
from ...kit import CallCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import PythonValueResolver
from .book import CallBook
from .idioms import RequestMethodIdiom, UrlopenIdiom, VerbIdiom
from .methods import MethodOptions
from .pending import PendingRequest, RequestRun
from .settle import Settler
from .sites import SiteHints


class RequestCalls(CallCollector):
    """Finds each request call, resolves its URL and method, and settles it at the call site (and, through wrapper
    functions, at the callers that supply its open parameters)."""

    IDIOMS = (UrlopenIdiom, RequestMethodIdiom, VerbIdiom)
    SPLATS = ('list_splat', 'dictionary_splat')
    MAX_ALTS = 4  # URL values one request may resolve to

    def __init__(self, workspace):
        super().__init__(workspace)
        self._values = PythonValueResolver(workspace)
        self._methods = MethodOptions(workspace, self._values)
        self._sites = SiteHints(workspace)
        self._book = CallBook(self)
        self._settler = Settler(workspace, self._book, self._values, self._methods, self._sites)
        self._idioms = {name: idiom(self._methods) for idiom in self.IDIOMS for name in idiom.NAMES}

    def collect(self) -> Extraction:
        for source, call, name in self.workspace.calls(self._idioms):
            self._request(source, call, self._idioms[name], name)
        return Extraction(calls=self._book.calls())

    def _request(self, source, call, idiom, name):
        receiver = PythonSyntax.receiver(call)
        pos, kw = PythonSyntax.call_args(call)
        scope = Scope.at(source, call)
        target = idiom.target(name, scope, receiver, pos, kw)
        if target is None or target.url is None or target.url.type in self.SPLATS:
            return
        methods = target.methods
        if methods is None:
            methods = self._methods.options(scope, target.method_node) if target.method_node is not None else [ANY]
        hints = self._sites.hints_for(scope, receiver)
        origin = self._sites.origin_assumption(scope, receiver)
        assumptions = (origin,) if origin is not None else ()
        run = RequestRun(target.client)
        for v in self._values.resolve(target.url, scope)[: self.MAX_ALTS]:
            for m in methods:
                pending = PendingRequest(v.text, m, hints | v.hints, assumptions=assumptions)
                self._settler.settle(scope, call, pending, run)
