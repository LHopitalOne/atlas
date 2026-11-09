"""ChannelReader: the channels one file sends on (calls) and receives on (routes)."""

from .....core.http import Call, Extraction, PathTemplate, Route
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from .matcher import Matcher
from .readings import ChannelReadings
from .table import Role


class ChannelReader:
    """Matches every call and `new` expression of a file against the table and turns each sending or receiving
    match into one call or route per channel it names."""

    NODES = frozenset({'call_expression', 'new_expression'})
    MAX_HINT = 200  # longer hints are cut

    def __init__(self, workspace, file):
        self._workspace = workspace
        self._file = file
        self._matcher = Matcher(file)
        self._readings = ChannelReadings(file)

    def read(self) -> Extraction:
        out = Extraction()
        for node in JsSyntax.walk(self._file.module.source.root, self.NODES):
            match = self._matcher.match(node)
            if match is None or match.entry.role == Role.MAKE:
                continue
            hints = set()
            for path in self._readings.of(match, hints):
                if match.entry.role == Role.SEND:
                    out.calls.append(self._call(match, path, hints))
                else:
                    out.routes.append(self._route(match, path))
        return out

    def _route(self, match, path):
        function, _ = Functions.enclosing(match.node)
        return Route(
            self._workspace.repo,
            self._file.path,
            JsSyntax.line(match.node),
            PathTemplate.parse(path),
            frozenset(match.entry.methods),
            handler=function,
            framework=match.library or match.entry.protocol,
            protocol=match.entry.protocol,
        )

    def _call(self, match, path, hints):
        function, owner = Functions.enclosing(match.node)
        fn = match.node.child_by_field_name('function')
        receiver = fn.child_by_field_name('object') if fn is not None and fn.type == 'member_expression' else None
        found = {*hints, function, owner, self._file.path, JsSyntax.text(receiver)}
        return Call(
            self._workspace.repo,
            self._file.path,
            JsSyntax.line(match.node),
            PathTemplate.parse(path),
            match.entry.methods[0],
            function,
            frozenset(h[: self.MAX_HINT] for h in found if h),
            test=self._workspace.is_test(self._file.module.source, match.node),
            protocol=match.entry.protocol,
        )
