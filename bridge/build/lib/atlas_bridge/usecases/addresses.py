"""Use case: which service an address, a host or a configured URL name points at, learned from configuration."""

from ..core.addresses import Address


class AddressBook:
    """Built from the ServiceUrls the extractors found and a function that says which repository a set of words
    names (ServiceNames.owner). A URL whose name or host names exactly one repository teaches three things:

    - its address (`localhost:18381`, `edx.devstack.discovery:18381`, `10.0.0.5:8000`) belongs to that repository;
    - its host, when it is not generic (`edx.devstack.discovery`, not `localhost` or an IP), does too;
    - its name, when the name itself names the repository (`COURSE_CATALOG_API_URL`, not `url`), points there;
    - its path ('/api/v1') is a prefix requests to it carry.

    An address or host two repositories claim is dropped: it tells nothing.
    """

    def __init__(self, urls, owner):
        self._addresses, self._hosts, self._names, self._prefixes = {}, {}, {}, {}
        conflicts = set()
        for url in urls:
            repo = owner({url.name} | (set() if url.generic_host else {url.host}))
            if repo is None:
                continue
            self._claim(self._addresses, url.address, repo, conflicts)
            if not url.generic_host:
                self._claim(self._hosts, url.host, repo, conflicts)
            if owner({url.name}) == repo:  # 'CATALOG_API_URL' names it; 'url' pointing at sentry.io does not
                self._claim(self._names, url.name, repo, conflicts)
            if url.path.literals and url.path.is_api:
                self._prefixes.setdefault(repo, set()).add(str(url.path))
        for table in (self._addresses, self._hosts, self._names):
            for key in conflicts & set(table):
                del table[key]

    @staticmethod
    def _claim(table, key, repo, conflicts):
        if not key:
            return
        if table.setdefault(key, repo) != repo:
            conflicts.add(key)

    def repos_for(self, hint: str) -> set[str]:
        """The repositories a hint points at: an address or URL with a port, a known host, or a configured name
        (the last name of 'settings.COURSE_CATALOG_API_URL' or 'getConfig().LMS_BASE_URL')."""
        found = set()
        address = Address.of_hint(hint)
        if address is not None:
            host, port = address
            repo = self._addresses.get(f'{host}:{port}')
            if repo is None and not Address.is_generic(host):
                repo = self._hosts.get(host)
            found |= {repo} if repo else set()
        elif hint.lower() in self._hosts:
            found.add(self._hosts[hint.lower()])
        name = hint.rsplit('.', 1)[-1]
        if name in self._names:
            found.add(self._names[name])
        return found

    def prefixes(self, repo) -> set[str]:
        """The API path prefixes configured URLs to `repo` carry ('/api/v1')."""
        return self._prefixes.get(repo, set())
