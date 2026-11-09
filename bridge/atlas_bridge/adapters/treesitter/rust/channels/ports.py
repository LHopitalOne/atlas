"""The port a socket address names, as the channel a TCP or UDP link travels on."""

import re


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
