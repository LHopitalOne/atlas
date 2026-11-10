"""Global request functions: fetch, axios, got, ky, and the EventSource a browser opens a Server-Sent Events stream
with."""

from ..syntax.nodes import JsSyntax
from ..syntax.site import CallSite
from .base import RequestCollector


class DirectRequests(RequestCollector):
    """`fetch(url, {method})`, `window.fetch(url)`, `axios(config)`, `axios(url, {method})`, `got(url)`, `ky(url)`;
    `new EventSource(url, {withCredentials})` is a GET of its URL."""

    NAMES = frozenset(CallSite.DIRECT + CallSite.STREAMS)

    def claims(self, module, site):
        return super().claims(module, site) and (not site.is_member or site.on_global())

    def requests(self, builder, site):
        if not site.args:
            return []
        first = JsSyntax.unwrap(site.args[0])
        if site.name == 'axios' and first.type == 'object':
            return builder.from_config(site.node, None, first)
        options = site.args[1] if len(site.args) > 1 else None
        return builder.build(site.node, None, site.args[0], builder.method(options, 'GET'), options=options)
