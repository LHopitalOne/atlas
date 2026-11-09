"""Use case: background tasks and work queues handled in the repository that sends them."""

from ..core.http import Call, Protocol
from ..core.model import Status
from .link import Link, LinkRule


class OwnChannelRule(LinkRule):
    """A task handed to workers (Celery's .delay(), a BullMQ queue.add()) or a message put on a work queue is usually
    handled by the same codebase: the worker is another process of the same repository. Such a call links to its own
    repository's route for the channel, when no other repository serves it (that case stays with the rules for other
    repositories). Every fixed segment of the call must meet the same text, so '/emails/welcome' fits
    '/emails/welcome' and a worker that takes every job of its queue ('/emails/{job}'), not '/{name}'."""

    PROTOCOLS = frozenset({Protocol.TASK, Protocol.AMQP})

    def applies(self, call: Call) -> bool:
        return bool(self._own(call))

    def links(self, call: Call) -> list[Link]:
        routes = self._own(call)
        status = Status.MATCHED if len(routes) == 1 else Status.AMBIGUOUS
        return self._each(call, call.repo, call.repo, routes, status, 'handled by a worker of the same repository')

    def _own(self, call):
        if call.protocol not in self.PROTOCOLS or call.path is None or not call.path.literals:
            return []
        if any(self._routes.best(call, repo)[1] for repo in self._routes.repos() if repo != call.repo):
            return []  # another repository serves it
        _, best = self._routes.best(call, call.repo)
        return [r for r in best if r.path.literals and self._literals_meet(call.path, r.path)]

    @staticmethod
    def _literals_meet(sent, served):
        """Every fixed segment of the route is the call's segment at the same place (a parameter takes anything)."""
        if len(served.segments) != len(sent.segments):
            return False
        return all(
            not r.is_literal or (s.is_literal and s.text == r.text)
            for s, r in zip(sent.segments, served.segments, strict=True)
        )
