"""RequestCalls: every request idiom in one pass over the call sites."""

from .base import RequestCollector
from .clients import ClientFetch, RequestMethods
from .direct import DirectRequests
from .verbs import VerbRequests


class RequestCalls(RequestCollector):
    """Hands each call site to the first idiom that claims it, so requests come out in source order and each file's
    bindings are resolved in that order too."""

    IDIOMS = (DirectRequests, ClientFetch, RequestMethods, VerbRequests)  # asked in this order

    def __init__(self, workspace):
        super().__init__(workspace)
        self._by_name = {}  # callee name -> the idioms that may claim it, in order
        for idiom in (cls(workspace) for cls in self.IDIOMS):
            for name in idiom.NAMES:
                self._by_name.setdefault(name, []).append(idiom)

    def visit(self, builder, site):
        idiom = self._idiom(builder.module, site)
        return idiom.requests(builder, site) if idiom is not None else []

    def claims(self, module, site):
        return self._idiom(module, site) is not None

    def requests(self, builder, site):
        return self.visit(builder, site)

    def _idiom(self, module, site):
        return next((i for i in self._by_name.get(site.name, ()) if i.claims(module, site)), None)
