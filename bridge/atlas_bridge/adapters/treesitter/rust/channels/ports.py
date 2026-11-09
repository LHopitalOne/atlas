"""The channel an entry point's argument names: the port of a socket address (TCP, UDP), or a topic name (Kafka)."""

import re

from ..syntax import RustSyntax
from .table import EntryPoints


class SocketAddress:
    """'127.0.0.1:5000', '[::1]:6000', 'localhost:9000/' -> '/5000', '/6000', '/9000'. An address whose port is not
    known, or is 0 (any free port: the caller's own end, never a service's), names no channel."""

    PORT = re.compile(r':(\d{1,5})/?$')  # the port at the end of 'host:port'
    MAX_PORT = 65535

    @classmethod
    def channel(cls, value: str) -> str | None:
        m = cls.PORT.search(value.strip())
        port = int(m.group(1)) if m else 0
        return f'/{port}' if 0 < port <= cls.MAX_PORT else None

    @classmethod
    def channels(cls, values) -> list[str]:
        """The channels of several values, each once, in order."""
        return list(dict.fromkeys(c for c in map(cls.channel, values) if c is not None))


class TopicNames:
    """'orders.created' -> '/orders.created'. A name only partly known ('{}' where it is not) names no channel, nor does
    a subscription pattern: librdkafka reads a topic starting with '^' as a regular expression."""

    NAME = re.compile(r'^[A-Za-z0-9._-]+$')  # a whole, legal Kafka topic name: no unknown parts, no '^' pattern

    @classmethod
    def channels(cls, values) -> list[str]:
        return list(dict.fromkeys('/' + v for v in values if cls.NAME.match(v)))


class SiteChannels:
    """The channels of one entry-point call (ChannelSite), read as its entry point's shape says."""

    ARRAYS = frozenset({'array_expression'})

    def __init__(self, values):
        self._values = values  # ChannelValues

    def of(self, file, site) -> list[str]:
        shape = site.entry.shape
        if shape == EntryPoints.ADDRESS:
            return SocketAddress.channels([v.text for v in self._values.values(file, site.address)])
        nodes = [site.address]
        if shape == EntryPoints.NAMES:
            items = RustSyntax.unwrap(site.address)
            nodes = items.named_children if items is not None and items.type in self.ARRAYS else []
        return TopicNames.channels(v.text for n in nodes for v in self._values.values(file, n))
