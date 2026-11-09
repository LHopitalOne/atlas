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
