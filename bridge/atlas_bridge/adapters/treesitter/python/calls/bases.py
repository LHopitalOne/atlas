"""The base URL a client object was made with, and how a request's relative URL is joined onto it."""

from ..qualified import QualifiedNames
from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker, Value


class ClientBases:
    """`httpx.Client(base_url=...)` (and `AsyncClient`): a request made on the client with a relative URL goes to
    the base URL with the request's path appended (httpx keeps the base's path, '/trpc' + '/notes.due' ->
    '/trpc/notes.due'). The client is the receiver's origin (SiteHints.origin_node): a local, a module-level name or
    an attribute of the class. Clients whose base is not given this way leave the URL as it is written."""

    CLIENTS = ('Client', 'AsyncClient')  # httpx's client classes
    LIBRARY = 'httpx'
    KEYWORD = 'base_url'
    MAX_BASES = 2  # values one base URL may resolve to
    SCHEME = '://'

    def __init__(self, workspace, values, sites):
        self._names = QualifiedNames(workspace)
        self._values = values  # PythonValueResolver
        self._sites = sites  # SiteHints

    def of(self, scope, receiver) -> list[Value]:
        """The values of the base URL the receiver's client was made with ([] when it has none we can read). Markers
        of the parameters of the function that made the client are written as {name}: that function is not the
        request's, so its callers do not fill them."""
        found = self._sites.origin_node(scope, receiver) if receiver is not None else None
        if found is None or found[1].type != 'call':
            return []
        source, call = found
        fn = self._names.of(source, call.child_by_field_name('function'))
        if not any(QualifiedNames.matches(fn, self.LIBRARY, name) for name in self.CLIENTS):
            return []
        base = PythonSyntax.call_args(call)[1].get(self.KEYWORD)
        if base is None:
            return []
        values = self._values.resolve(base, Scope.at(source, call))[: self.MAX_BASES]
        return [Value(Marker.braces(v.text), v.hints) for v in values if v.is_known]

    @classmethod
    def join(cls, base: Value, url: Value) -> Value:
        """The URL a request for `url` on a client with this base goes to: the base's URL with the path appended for
        a URL that starts with a literal path; an absolute URL, or one a caller still gives, as it is."""
        text = url.text
        if cls.SCHEME in text or text.startswith(('{', Marker.OPEN)):
            return url
        return Value(base.text.rstrip('/') + '/' + text.lstrip('/'), base.hints | url.hints, url.kind)
