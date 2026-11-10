"""Routes a server writes as a `match` on a request's method and path (tiny_http, hyper without a router):
`match (request.method(), request.url()) { (Method::Get, "/scores") => ..., _ => not_found }`."""

from .....core.http import ANY, Extraction
from ...kit import RouteCollector, StringTemplate
from ..syntax import RustSyntax


class MatchRoutes(RouteCollector):
    """One route per arm of a `match` whose scrutinee is the (method, path) pair of a request, read from a value of a
    request type of REQUESTS: tiny_http's `request.url()`, hyper's and http's `req.uri().path()`. An arm's pattern
    is a (method, path literal) tuple; `_` for the method takes any. Arms with any other path pattern are skipped."""

    framework = 'match'
    REQUESTS = frozenset({'tiny_http::Request', 'hyper::Request', 'http::Request'})
    METHOD = 'method'
    PATHS = (('url',), ('uri', 'path'))  # the calls that read a request's path, innermost first
    MENTIONS = (b'tiny_http', b'hyper', b'http')
    PUNCTUATION = frozenset({'(', ')', ','})  # a tuple pattern's other children; `_` is an unnamed one

    def __init__(self, workspace, types):
        super().__init__(workspace)
        self._types = types

    def collect(self) -> Extraction:
        out = Extraction()
        for f in self.workspace.files:
            if not f.mentions(*self.MENTIONS):
                continue
            for fn in (fn for fn in f.nodes('fn') if not self.workspace.is_test(f, fn)):
                for match in RustSyntax.walk(fn, ('match_expression',)):
                    out.routes += self._routes(f, fn, match)
        return out

    def _routes(self, file, fn, match):
        scrutinee = RustSyntax.unwrap(match.child_by_field_name('value'))
        if scrutinee is None or scrutinee.type != 'tuple_expression' or len(scrutinee.named_children) != 2:
            return []
        method, path = scrutinee.named_children
        request = self._request(method, (self.METHOD,))
        if request is None or self._types.of(file, request) not in self.REQUESTS:
            return []
        reads = (self._request(path, chain) for chain in self.PATHS)
        if not any(r is not None and RustSyntax.text(r) == RustSyntax.text(request) for r in reads):
            return []
        body = match.child_by_field_name('body')
        arms = [a for a in body.named_children if a.type == 'match_arm'] if body is not None else []
        return [r for r in (self._route(file, fn, arm) for arm in arms) if r is not None]

    @staticmethod
    def _request(node, chain):
        """The value a chain of argument-less method calls is made on (`req` in `req.uri().path()`), or None."""
        for name in reversed(chain):
            node = RustSyntax.unwrap(node)
            fn = RustSyntax.method(node) if node is not None and node.type == 'call_expression' else None
            if fn is None or RustSyntax.args(node) or RustSyntax.text(fn.child_by_field_name('field')) != name:
                return None
            node = fn.child_by_field_name('value')
        return RustSyntax.unwrap(node)

    def _route(self, file, fn, arm):
        pattern = arm.child_by_field_name('pattern')
        tuple_ = pattern.named_children[0] if pattern is not None and pattern.named_children else None
        parts = [c for c in tuple_.children if c.type not in self.PUNCTUATION] if tuple_ is not None else []
        if tuple_ is None or tuple_.type != 'tuple_pattern' or len(parts) != 2:
            return None
        method, path = parts
        if path.type not in RustSyntax.STRINGS:
            return None
        text = StringTemplate.of(path)
        if not text or not text.startswith('/'):
            return None
        methods = self._methods(method)
        return self.route(file, file.line(arm), text, methods, RustSyntax.name(fn)) if methods else None

    @staticmethod
    def _methods(pattern):
        """{'GET'} for `Method::Get` or `&Method::GET`, {ANY} for `_`, empty for anything else."""
        if pattern.type == 'reference_pattern' and pattern.named_children:
            pattern = pattern.named_children[0]
        if RustSyntax.text(pattern) == '_':
            return frozenset({ANY})
        if pattern.type != 'scoped_identifier':
            return frozenset()
        return frozenset({RustSyntax.text(pattern.child_by_field_name('name')).upper()})
