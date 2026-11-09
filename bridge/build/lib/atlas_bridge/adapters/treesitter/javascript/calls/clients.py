"""Requests sent with the fetch / request methods of a client: `api.fetch(url)`, `api.request(config)`."""

from ..bindings.receivers import Receivers
from ..syntax.nodes import JsSyntax
from ..syntax.site import CallSite
from .base import RequestCollector


class ClientRequests(RequestCollector):
    """Requests sent with a method of a client object, given a URL and options or a config object."""

    def _request(self, builder, site, require_path):
        args, obj = site.args, site.receiver
        if not args:
            return []
        first = JsSyntax.unwrap(args[0])
        if first.type == 'object':
            return builder.from_config(site.node, obj, first) if not require_path else []
        if require_path and builder.module.receivers.is_not_client(obj):
            return []
        options = args[1] if len(args) > 1 else None
        return builder.build(site.node, obj, args[0], builder.method(options, 'GET'), require_path)


class ClientFetch(ClientRequests):
    """`api.fetch(url)` on a receiver named like an HTTP client."""

    NAMES = frozenset({'fetch'})

    def claims(self, module, site):
        return (
            super().claims(module, site)
            and site.is_member
            and not site.on_global()
            and Receivers.is_client(site.receiver)
        )

    def requests(self, builder, site):
        return self._request(builder, site, require_path=False)


class RequestMethods(ClientRequests):
    """`api.request(config)`, `api.requestPromise(url, {method})`. On a receiver not named like a client, only a
    path-like URL is a request."""

    NAMES = frozenset(CallSite.REQUEST_METHODS)

    def claims(self, module, site):
        return super().claims(module, site) and site.is_member

    def requests(self, builder, site):
        return self._request(builder, site, require_path=not Receivers.is_client(site.receiver))
