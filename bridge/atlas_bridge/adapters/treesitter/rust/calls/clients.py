"""Requests sent through an HTTP client: `client.get(url)`, `.request(Method::X, url)`, `reqwest::get(url)`."""

import re

from .....core.http import ANY
from ...kit import UrlTemplate
from ..names import ItemPath
from ..syntax import RustSyntax
from ..values import UrlPiece, Value
from .base import RustCallCollector
from .context import RequestContext


class ClientCalls(RustCallCollector):
    """A call with a method and a URL. Calls whose URL does not look like a path are kept only when the receiver
    is named like a client, so `map.get(key)` is not a request."""

    CAPTURE = 'call'
    VERBS = frozenset({'get', 'post', 'put', 'patch', 'delete', 'head'})
    CLIENT = re.compile(r'client|http|reqwest|request|upstream', re.I)  # a name that suggests an HTTP client
    METHOD = re.compile(r'(?:^|::)Method::([A-Z]+)$')  # a whole argument naming a method: `reqwest::Method::POST`
    MAX_HINT = 300  # longer hints are whole expressions, not names
    SCHEME = re.compile(r'^[a-z][a-z0-9+.-]*://[^/{}]+', re.I)  # an absolute URL whose host is known

    def __init__(self, workspace, values, configured=None):
        super().__init__(workspace, values)
        self._context = RequestContext(workspace)
        self._configured = configured  # ChannelValues: what a base URL holds once fields and settings are followed

    def calls(self, file, c) -> list:
        request = self._request(c)
        if request is None:
            return []
        method, url, recv = request
        vals = self._values.values(file, url)
        if not vals:
            vals = [Value(v, url, []) for v in self._absolute(file, url)][:1]
        if not vals:
            return []
        value, _, base = vals[0]
        if value.startswith('{}'):
            value = self._based(file, url, value)
        if not self._addressed(value, recv):
            return []
        split = UrlTemplate.split(value)
        if split.path is None:
            return []
        hints = {RustSyntax.text(recv), RustSyntax.text(url), file.path, *base, *split.hints}
        hints |= {RustSyntax.text(n) for n in RustSyntax.identifiers(url)}
        hints |= self._context.hints(file, c, recv)
        hints = {h for h in hints if h and len(h) < self.MAX_HINT}
        function = self._context.function_name(c)
        return [self.call(file, file.line(c), split.path, method, function, hints, self.workspace.is_test(file, c))]

    def _absolute(self, file, url):
        """The absolute URLs a URL expression holds once struct fields, crate fns (`self.endpoint(path)`) and
        environment defaults are followed; unknown parts are '{}'."""
        if self._configured is None:
            return []
        return [v.text for v in self._configured.values(file, url) if self.SCHEME.match(v.text)]

    def _based(self, file, url, value):
        """A URL on an unknown base (`format!("{}/item/{}.json", self.base, id)`) with the base it is configured
        with, when every absolute URL the expression holds agrees on it; the value as it was otherwise."""
        tail = UrlPiece.PLACEHOLDER.sub('{}', value[2:])
        bases = {v[: len(v) - len(tail)] for v in self._absolute(file, url) if v.endswith(tail)}
        return bases.pop() + value[2:] if len(bases) == 1 else value

    def _addressed(self, value, recv):
        """A path or URL, or any string handed to something named like a client."""
        return UrlPiece.path_like(value) or bool(self.CLIENT.search(RustSyntax.receiver_name(recv)))

    def _request(self, c):
        """(method, url node, receiver node) of a request call, or None."""
        fn = c.child_by_field_name('function')
        if fn is None:
            return None
        args = RustSyntax.args(c)
        m = self.METHOD.search(RustSyntax.text(args[0])) if args else None
        if m and len(args) >= 2:  # `.request(Method::X, url)`, `Request::new(Method::X, url)`
            recv = fn.child_by_field_name('value') if fn.type == 'field_expression' else fn
            return m.group(1), args[1], recv
        if fn.type == 'field_expression':
            return self._method_request(fn, args)
        if fn.type == 'scoped_identifier' and len(args) == 1:
            return self._function_request(fn, args)
        return None

    def _method_request(self, fn, args):
        """`client.get(url)`, `client.request(method, url)`."""
        name = RustSyntax.text(fn.child_by_field_name('field'))
        if len(args) == 1:
            return (name.upper(), args[0], fn.child_by_field_name('value')) if name in self.VERBS else None
        if len(args) == 2 and name == 'request':
            return ANY, args[1], fn.child_by_field_name('value')
        return None

    def _function_request(self, fn, args):
        """`reqwest::get(url)`, `http_client::post(url)`."""
        segs = ItemPath.segments(fn)
        if not (segs[-1] in self.VERBS and len(segs) > 1 and self.CLIENT.search('::'.join(segs[:-1]))):
            return None
        return segs[-1].upper(), args[0], fn
