"""Use case: links inside one repository, from its browser code to its own server's routes (a monorepo's frontend
calling its backend)."""

from ..core.http import Call
from ..core.model import Status
from .link import Link, LinkRule


class WithinRepoRule(LinkRule):
    """A request from browser code to a relative path ('/api/0/auth') goes to the origin that served the page: in a
    repository that holds both, its own server. It counts when every fixed word of the path meets the same word in
    one of the repository's routes, so a catch-all or a route of parameters never takes it, and a path that ends in
    an unknown rest ('/api/0/{*url}') only when one route fits. A call whose hints name another repository is left to
    the rules before this one."""

    FRONTEND = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.vue', '.svelte')
    LITERAL_POINTS = 3  # what a literal-on-literal segment scores in PathTemplate.fit

    def applies(self, call: Call) -> bool:
        return bool(self._own(call))

    def links(self, call: Call) -> list[Link]:
        routes = self._own(call)
        status = Status.MATCHED if len(routes) == 1 else Status.AMBIGUOUS
        return self._each(call, call.repo, call.repo, routes, status, 'browser code calls its own repository')

    def _own(self, call):
        if call.path is None or not call.path.literals or not call.file.endswith(self.FRONTEND):
            return []
        top, best = self._routes.best(call, call.repo)
        if top < self.LITERAL_POINTS * call.path.literals or (call.path.has_rest and len(best) > 1):
            return []  # a word met a parameter, or '/api/0/{*url}' (a generic helper) fits every route under it
        return best


class NoRouteRule(LinkRule):
    """Browser code that calls its own server under a prefix the server's routes use ('/api/v1/retrieval/...') but
    that no route serves and none could take: a request with no route (a call left behind when an endpoint was
    removed, or one served by code that is not on the map). It is reported, not linked. A path written as an
    absolute URL, or sharing less than MIN_PREFIX fixed words with any route, says too little about where it goes."""

    MIN_PREFIX = 2  # '/api/v1': fewer shared words do not show the request is meant for this server

    def applies(self, call: Call) -> bool:
        return self._prefix(call) is not None

    def links(self, call: Call) -> list[Link]:
        prefix = self._prefix(call)
        why = f'no route of {call.repo} serves it, though its routes under {prefix} do ({call.method} {call.path})'
        return [Link(call, call.repo, call.repo, None, Status.UNMATCHED, why)]

    def _prefix(self, call):
        """The longest run of leading fixed words the call shares with a route of its repository, when it is long
        enough and the call goes on past it; else None."""
        if call.path is None or call.host or call.protocol != 'http' or not call.file.endswith(WithinRepoRule.FRONTEND):
            return None
        if self._routes.best(call, call.repo)[1]:
            return None  # a route could take it ('/users/me' by '/users/{user_id}'), only not surely enough to link
        sent = call.path.segments
        best = 0
        for r in self._routes.routes(call.repo):
            n = 0
            for a, b in zip(sent, r.path.segments, strict=False):
                if not (a.is_literal and b.is_literal and a.text == b.text):
                    break
                n += 1
            best = max(best, n)
        if best < self.MIN_PREFIX or best >= len(sent) or not sent[best].is_literal:
            return None
        return '/' + '/'.join(s.text for s in sent[:best])
