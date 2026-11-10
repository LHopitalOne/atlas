"""Where services are reachable: URLs that configuration gives a name, and the host:port addresses inside them.

`COURSE_CATALOG_API_URL = 'http://edx.devstack.discovery:18381/api/v1'` in a settings module, `LMS_BASE_URL=
'http://localhost:18000'` in an .env file and a docker-compose service publishing '18381:18381' each say that a
name (and so a service) is reachable at an address, and under which path prefix.
"""

import ipaddress
import re
from dataclasses import dataclass, field

from .http import PathTemplate


class Address:
    """Reading hosts and host:port pairs: `localhost`, IPs and Docker's host alias name no service on their own."""

    URL = re.compile(
        r'^[a-z][a-z0-9+.-]*://(?P<host>\[[0-9a-f:.]+\]|[^/:?#\s]+)(?::(?P<port>\d+))?(?P<path>/[^?#\s]*)?', re.I
    )  # scheme://host:port/path, the host an IPv6 literal in brackets or a name
    HOST_PORT = re.compile(r'^(?P<host>\[[0-9a-f:.]+\]|[\w.-]+):(?P<port>\d+)$', re.I)  # 'localhost:18381'
    LOCAL = frozenset({'localhost', '0.0.0.0', 'host.docker.internal', 'gateway.docker.internal', '[::1]', '[::]'})

    @classmethod
    def is_generic(cls, host: str) -> bool:
        """A host that is the same machine or a bare IP: only its port can tell services apart."""
        h = host.lower()
        if h in cls.LOCAL:
            return True
        try:
            ipaddress.ip_address(h.strip('[]'))
        except ValueError:
            return False
        return True

    @classmethod
    def of_hint(cls, hint: str) -> tuple[str, str] | None:
        """(host, port) of a hint written 'host:port' or as an absolute URL with a port; None otherwise."""
        m = cls.HOST_PORT.match(hint) or cls.URL.match(hint)
        if m is None or not m.group('port'):
            return None
        return m.group('host').lower(), m.group('port')


@dataclass(frozen=True)
class ServiceUrl:
    """A URL that configuration gives a name: the setting, env variable or compose service, and where it points."""

    repo: str
    file: str
    line: int
    name: str
    host: str
    port: str = ''
    path: PathTemplate = field(default_factory=lambda: PathTemplate(()))

    @classmethod
    def parse(cls, repo, file, line, name, url) -> 'ServiceUrl | None':
        """The ServiceUrl of an absolute URL ('http://host:port/path'), or None when the value is not one."""
        m = Address.URL.match(url.strip())
        if m is None:
            return None
        path = PathTemplate.parse(m.group('path') or '/')
        return cls(repo, file, line, name, m.group('host').lower(), m.group('port') or '', path)

    @property
    def address(self) -> str:
        """'host:port', or '' without a port."""
        return f'{self.host}:{self.port}' if self.port else ''

    @property
    def generic_host(self) -> bool:
        return Address.is_generic(self.host)
