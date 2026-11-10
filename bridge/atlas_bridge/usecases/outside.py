"""Use case: requests that leave the repositories, to a host none of them serves."""

import re

from ..core.addresses import Address
from ..core.http import Call
from ..core.model import Status
from .link import Link, LinkRule


class OutsideRule(LinkRule):
    """A request to an absolute URL whose host no repository here serves (`https://api.linkedin.com/v2/me`, a CDN
    script, an analytics beacon) goes outside: it links to that host. A local or private address, a placeholder
    domain, or a host a repository's name or configuration claims is not outside; it is left unknown."""

    HOSTNAME = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,24}$')  # 'api.linkedin.com'
    PLACEHOLDERS = re.compile(r'(?:^|\.)(?:example|localhost|local|internal|test|invalid)(?:\.[a-z]+)?$')

    def applies(self, call: Call) -> bool:
        host = call.host
        if not host or Address.is_generic(host) or not self.HOSTNAME.match(host) or self.PLACEHOLDERS.search(host):
            return False
        return not self._names.resolve([host], exclude=None)

    def links(self, call: Call) -> list[Link]:
        host = call.host
        return [
            Link(
                call, call.repo, host, None, Status.OUTSIDE, f'sent to {host}, which none of these repositories serves'
            )
        ]
