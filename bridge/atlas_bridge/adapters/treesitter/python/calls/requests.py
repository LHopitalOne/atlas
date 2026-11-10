"""RequestCalls: HTTP requests sent with requests/httpx/aiohttp/urllib3/urllib-style clients."""

from .....core.http import ANY, Extraction
from ...kit import CallCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import PythonValueResolver
from .bases import ClientBases
from .book import CallBook
from .idioms import RequestMethodIdiom, RequestTarget, UrlopenIdiom, VerbIdiom
from .methods import MethodOptions
from .pending import PendingRequest, RequestRun
from .senders import Senders
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
        self._senders = Senders(workspace)
        self._bases = ClientBases(workspace, self._values, self._sites)

    def collect(self) -> Extraction:
        for source, call, name in self.workspace.calls(self._idioms):
            self._request(source, call, self._idioms[name], name)
        return Extraction(calls=self._book.calls())

    def _request(self, source, call, idiom, name):
        if call.parent is not None and call.parent.type == 'decorator':
            return  # `@routes.get('/healthz')` declares a route; a decorator never sends a request
        sends = self._senders.verdict(source, call, name)
        if sends is False:
            return  # the index says it reaches something else: a wrapper whose own request is found inside it
        receiver = PythonSyntax.receiver(call)
        pos, kw = PythonSyntax.call_args(call)
        scope = Scope.at(source, call)
        target = idiom.target(name, scope, receiver, pos, kw)
        if target is None and sends and receiver is not None:  # syntax took it for mapping.get(key, default)
            target = RequestTarget(kw.get('url', pos[0] if pos else None), None, [name.upper()], True)
        if target is None or target.url is None or target.url.type in self.SPLATS:
            return
        if sends:
            target = target._replace(client=True)
        methods = target.methods
        if methods is None:
            methods = self._methods.options(scope, target.method_node) if target.method_node is not None else [ANY]
        hints = self._sites.hints_for(scope, receiver)
        origin = self._sites.origin_assumption(scope, receiver)
        assumptions = (origin,) if origin is not None else ()
        run = RequestRun(target.client)
        for v in self._urls(target.url, scope, receiver):
            for m in methods:
                pending = PendingRequest(v.text, m, hints | v.hints, assumptions=assumptions)
                self._settler.settle(scope, call, pending, run)

    def _urls(self, url, scope, receiver):
        """The values of a request's URL, each joined onto the base URL of its client when the client has one."""
        values = self._values.resolve(url, scope)[: self.MAX_ALTS]
        bases = self._bases.of(scope, receiver)
        return [ClientBases.join(b, v) for v in values for b in bases] if bases else values
