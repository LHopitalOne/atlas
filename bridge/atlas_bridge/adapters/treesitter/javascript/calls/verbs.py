"""Verb requests: `api.get(url)`, `axios.delete(url)`, `this.client.post(url)`, `request(app).get(url)`, and a verb
given one options object holding the URL (`client.get({ url: '/pets/{id}', ...options })`)."""

from ..bindings.receivers import Receivers
from ..syntax.nodes import JsSyntax
from ..syntax.site import CallSite
from .base import RequestCollector


class VerbRequests(RequestCollector):
    """A verb method called on a client. A verb call that declares a route (`app.get('/p', h)`) is not a request; on
    a receiver not named like a client, only a path-like URL is one. A verb whose first argument is an object literal
    with a `url` sends to that URL with the verb's method: the shape the functions of generated SDKs have
    (@hey-api/openapi-ts: `(options?.client ?? client).get({ url: '/api/v1/stories/top', ...options })`)."""

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
        first = JsSyntax.unwrap(site.args[0])
        if first is not None and first.type == 'object':
            if self._module_function(builder.module, site.receiver):
                return []  # `api.patch({ url })` of `import * as api`: the module's own wrapper, followed as one
            return builder.from_config(site.node, site.receiver, first, method, require_path=not is_client)
        return builder.build(site.node, site.receiver, site.args[0], method, require_path=not is_client)

    @staticmethod
    def _module_function(module, receiver):
        """The receiver holds a whole module, so the verb is a function that module exports."""
        return receiver.type == 'identifier' and module.imports.namespace(JsSyntax.text(receiver)) is not None
