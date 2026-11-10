"""PayloadCalls: Django `reverse('route-name')` URLs made absolute and handed to another service, not requested."""

from .....core.http import ANY, Call, Extraction
from ...kit import CallCollector
from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker, PythonValueResolver
from .absolute import AbsoluteUrl
from .book import CallBook
from .hints import PayloadHints


class PayloadCalls(CallCollector):
    """A `reverse()` / `reverse_lazy()` of a literal route name, joined to a base URL (AbsoluteUrl), is a payload
    call: no path, the route's name, and hints naming the service that will fetch the URL."""

    NAMES = frozenset({'reverse', 'reverse_lazy'})
    MODULES = ('urls', 'urlresolvers')  # `urls.reverse(...)`: other receivers' reverse() is list.reverse()
    NAME_NODES = ('string', 'concatenated_string', 'identifier', 'attribute')
    NOT_IN_NAMES = frozenset('{}' + Marker.UNRESOLVED)  # placeholders or markers: not a literal route name

    def __init__(self, workspace):
        super().__init__(workspace)
        self._values = PythonValueResolver(workspace)
        self._hints = PayloadHints(workspace)
        self._book = CallBook(self)

    def collect(self) -> Extraction:
        for source, call, _ in self.workspace.calls(self.NAMES):
            self._payload(source, call)
        return Extraction(calls=self._book.calls())

    def _payload(self, source, call):
        receiver = PythonSyntax.receiver(call)
        if receiver is not None and not PythonSyntax.text(receiver).endswith(self.MODULES):
            return
        if not AbsoluteUrl.made_absolute(call):
            return
        pos, kw = PythonSyntax.call_args(call)
        node = kw.get('viewname', pos[0] if pos else None)
        if node is None or node.type not in self.NAME_NODES:
            return
        scope = Scope.at(source, call)
        v = self._values.resolve(node, scope)[0]
        if not v.is_literal or not self._is_route_name(v.text):
            return
        hints = {source.path, scope.qualified}
        if not self.workspace.is_test(source, call):
            hints |= self._hints.hints_for(scope)
        self._book.add(scope, call, None, ANY, hints, kind=Call.PAYLOAD, route_name=v.text)

    @classmethod
    def _is_route_name(cls, text):
        """A literal route name: not empty, no whitespace, placeholders or markers."""
        return bool(text) and not any(c.isspace() or c in cls.NOT_IN_NAMES for c in text)
