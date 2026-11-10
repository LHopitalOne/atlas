"""The links the Atlas map shows (HTTP, and topics, queues and tasks), read from the links JSON the `links`
command writes (adapters/linkfile.py).

Each record keeps what the page needs to prove a link: the line that sends the request, the route line that serves
it, and what a precise index said about the names in between.
"""

from dataclasses import dataclass

from ...core.errors import LinkFormatError


@dataclass(frozen=True)
class CallSite:
    """The line that sends the request."""

    repo: str
    file: str
    line: int
    function: str
    method: str
    path: str


@dataclass(frozen=True)
class RouteSite:
    """The route declaration that serves it."""

    repo: str
    file: str
    line: int
    methods: tuple[str, ...]
    path: str
    handler: str
    framework: str
    protocol: str = 'http'

    REQUESTS = frozenset({'http', 'websocket', 'graphql'})  # addressed by method and path; the others by channel

    @property
    def is_request(self):
        return self.protocol in self.REQUESTS

    @property
    def channel(self):
        """What the page shows after the method: the path, or a topic, queue or task by its bare name."""
        return self.path if self.is_request else self.path.strip('/')

    @property
    def label(self):
        """'GET|POST /api/x', or 'KAFKA events' for a channel that has no methods."""
        verb = '|'.join(self.methods) if self.is_request else self.protocol.upper()
        return f'{verb} {self.channel}'


@dataclass(frozen=True)
class Check:
    """One name the link rests on, and what SCIP said of it."""

    at: str
    name: str
    means: str
    verdict: str


@dataclass(frozen=True)
class LinkRecord:
    caller: str
    target: str
    status: str
    verification: str
    reason: str
    call: CallSite
    route: RouteSite | None
    checks: tuple[Check, ...]

    # how the page badges a link: (status, verification) -> proof; statuses other than matched need no verification
    PROOF = {'confirmed': 'scip', 'syntax': 'syntax', 'unverified': 'matched', 'contradicted': 'contradicted'}
    EDGE_STATUS = {
        'scip': 0,
        'syntax': 0,
        'matched': 0,
        'outside': 0,
        'contradicted': 1,
        'ambiguous': 1,
        'inferred': 3,
        'judged': 3,
    }

    @property
    def proof(self):
        """scip (confirmed by SCIP), syntax (read straight from the code), matched (read from the code, names not
        confirmed), contradicted, inferred, judged (chosen by a decision model), ambiguous or outside."""
        if self.verification == 'judged':
            return 'judged'  # chosen by a decision model among the routes the code left open
        if self.status != 'matched':
            return self.status
        return self.PROOF.get(self.verification, 'matched')

    @property
    def edge_status(self):
        return self.EDGE_STATUS.get(self.proof, 3)

    @property
    def sort_key(self):
        return (self.caller, self.target, self.call.file, self.call.line, self.call.path)


class LinkFile:
    """Parses the links JSON; production links only (calls made only by tests and tooling are left out)."""

    STATUSES = frozenset({'matched', 'ambiguous', 'inferred', 'unmatched', 'outside'})

    def __init__(self, source: str = 'links JSON'):
        self._source = source

    def parse(self, data: dict) -> list[LinkRecord]:
        if not isinstance(data, dict) or not isinstance(data.get('links'), list):
            raise LinkFormatError(self._source, 'it has no "links" list')
        records = [self._record(i, d) for i, d in enumerate(data['links'])]
        return sorted((r for r in records if r is not None), key=lambda r: r.sort_key)

    def _record(self, i, d):
        try:
            call = d['call']
            if call.get('test'):
                return None
            if d['status'] not in self.STATUSES:
                raise LinkFormatError(self._source, f'links[{i}] has status {d["status"]!r}')
            return LinkRecord(
                caller=d['caller'],
                target=d.get('target') or '',
                status=d['status'],
                verification=d.get('verification') or 'unverified',
                reason=d.get('reason') or '',
                call=self._call(d['caller'], call),
                route=self._route(d['route']) if d.get('route') else None,
                checks=tuple(self._check(a) for a in d.get('assumptions') or []),
            )
        except (KeyError, TypeError, AttributeError) as e:
            raise LinkFormatError(self._source, f'links[{i}] is missing {e}') from e

    @staticmethod
    def _call(repo, c):
        return CallSite(
            repo, c['file'], int(c['line']), c.get('function') or '', c.get('method') or '', c.get('path') or ''
        )

    @staticmethod
    def _route(r):
        return RouteSite(
            r['repo'],
            r['file'],
            int(r['line']),
            tuple(r.get('methods') or ['ANY']),
            r['path'],
            r.get('handler') or '',
            r.get('framework') or '',
            r.get('protocol') or 'http',
        )

    @staticmethod
    def _check(a):
        return Check(a.get('at') or '', a.get('name') or '', a.get('means') or '', a.get('verdict') or 'unknown')
