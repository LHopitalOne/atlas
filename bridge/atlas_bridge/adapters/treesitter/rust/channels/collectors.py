"""Channels both ways: calls that send to a socket address and routes that receive on one, from EntryPoints."""

import dataclasses

from .....core.http import Extraction
from ...kit import RouteCollector
from ..calls import RequestContext, RustCallCollector
from ..guard import StackGuard
from ..syntax import RustSyntax
from .ports import SiteChannels
from .table import EntryPoints


class ChannelCalls(RustCallCollector):
    """One call per port a sending entry point's address can hold (`TcpStream::connect(addr)`), with the names
    around it as hints; a connected UDP socket only when it then sends (EntryPoint.then)."""

    CAPTURE = 'call'

    def __init__(self, workspace, values, sites, followups):
        super().__init__(workspace, values)
        self._channels = SiteChannels(values)
        self._sites = sites
        self._followups = followups

    def calls(self, file, node) -> list:
        site = self._sites.site(file, node)
        if site is None or site.entry.role != EntryPoints.SEND:
            return []
        if site.entry.then and not self._followups.follows(file, site):
            return []
        function = RequestContext.function_name(node)
        hints = {file.path, function, RustSyntax.text(site.address)}
        hints |= {RustSyntax.text(i) for i in RustSyntax.identifiers(site.address)}
        hints = {h for h in hints if h}
        test = self.workspace.is_test(file, node)
        return [
            self.call(
                file, file.line(node), path, function=function, hints=hints, test=test, protocol=site.entry.protocol
            )
            for path in self._channels.of(file, site)
        ]


class ChannelRoutes(RouteCollector):
    """One route per port a receiving entry point binds (`TcpListener::bind(addr)`), outside test code; a UDP
    socket only when it is then read from (EntryPoint.then), a TCP listener only when no server takes it over
    (EntryPoint.unless)."""

    def __init__(self, workspace, values, sites, followups):
        super().__init__(workspace)
        self._channels = SiteChannels(values)
        self._sites = sites
        self._followups = followups

    def collect(self) -> Extraction:
        out = Extraction()
        for f in self.workspace.files:
            for node in f.nodes('call'):
                out.routes += StackGuard.run(self.routes, f, node)
        return out

    def routes(self, file, node) -> list:
        site = self._sites.site(file, node)
        if site is None or site.entry.role != EntryPoints.RECEIVE or self.workspace.is_test(file, node):
            return []
        if site.entry.then and not self._followups.follows(file, site):
            return []
        if site.entry.unless and self._followups.handed(node, site.entry.unless):
            return []
        handler = RequestContext.function_name(node)
        return [
            dataclasses.replace(self.route(file, file.line(node), path, handler=handler), protocol=site.entry.protocol)
            for path in self._channels.of(file, site)
        ]
