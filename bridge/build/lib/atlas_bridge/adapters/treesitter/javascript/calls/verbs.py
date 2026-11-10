"""Verb requests: `api.get(url)`, `axios.delete(url)`, `this.client.post(url)`, `request(app).get(url)`."""

from ..bindings.receivers import Receivers
from ..syntax.site import CallSite
from .base import RequestCollector


class VerbRequests(RequestCollector):
    """A verb method called on a client. A verb call that declares a route (`app.get('/p', h)`) is not a request; on
    a receiver not named like a client, only a path-like URL is one."""

    NAMES = frozenset(CallSite.ROUTE_VERBS)
    NOT_REQUESTS = frozenset({'all'})  # `app.all(...)` only declares routes

    def claims(self, module, site):
        if not (super().claims(module, site) and site.is_member):
            return False
        return module.route_syntax.declaration(site) is None

    def requests(self, builder, site):
        if not site.args or site.name in self.NOT_REQUESTS:
            return []
        method = CallSite.method_of(site.name)
        is_client = Receivers.is_client(site.receiver)
        if not is_client and builder.module.receivers.is_not_client(site.receiver):
            return []
        return builder.build(site.node, site.receiver, site.args[0], method, require_path=not is_client)
