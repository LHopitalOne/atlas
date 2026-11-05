"""Settling a request at a call site: emit it when it says more than the level below, forward what is still open."""

from .....core.http import ANY
from .forwarding import Forwarder
from .pending import PendingRequest, Reading


class Settler:
    """Emits requests into a CallBook and forwards open parameters to the callers of the enclosing function."""

    MAX_FORWARD = 4  # wrapper levels followed up to the caller that supplies the path

    def __init__(self, workspace, book, values, methods, sites):
        self._book = book
        self._forwarder = Forwarder(workspace, self, values, methods, sites)

    def settle(self, scope, site, pending: PendingRequest, run):
        """Emit the request at this call site if it says more than the level below, and forward open parameters."""
        if not run.spend():
            return
        reading = Reading.from_request(pending.url, pending.method, run.client)
        if reading.pathlike and pending.says_more(reading):
            method = ANY if reading.method_open else pending.method
            self._book.add(scope, site, reading.path, method, pending.hints | reading.bases)
        forwardable = reading.pathlike or run.client
        if reading.open and scope.func is not None and pending.depth < self.MAX_FORWARD and forwardable:
            self._forwarder.forward(scope, pending.seen_with(reading), run)
