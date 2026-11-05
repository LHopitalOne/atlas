"""Turning the URL argument of a request call into a PendingRequest: its path, hints, client and test flag."""

from .....core.http import ANY
from ...kit import UrlTemplate
from ..bindings.receivers import Receivers
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..values.urls import UrlText
from .pending import PendingRequest


class RequestBuilder:
    """Builds the requests of one file."""

    MAX_HINT = 200  # longer hints are cut

    def __init__(self, workspace, module):
        self._workspace = workspace
        self._module = module

    @property
    def module(self):
        return self._module

    def method(self, options, default):
        """The `method` of a request options object (literal, or a const bound to one); ANY when not a literal."""
        if options is None:
            return default
        options = JsSyntax.unwrap(options)
        if options.type == 'identifier':
            options = JsSyntax.unwrap(self._module.scopes.lookup(options, JsSyntax.text(options)))
            if options is None:
                return default
        if options.type != 'object':
            return default
        method = JsSyntax.prop(options, 'method')
        if method is None:
            return default
        method = JsSyntax.unwrap(method)
        if method.type == 'string':
            return (JsSyntax.string(method) or default).upper()
        return ANY

    def from_config(self, node, obj, config):
        """`axios({url, method})`, `api.request({url})`."""
        url = JsSyntax.prop(config, 'url')
        if url is None:
            return []
        return self.build(node, obj, url, self.method(config, 'GET'))

    def build(self, node, obj, url_node, method, require_path=False):
        """[the request] when `url_node` holds something to match a route with; [] when it does not."""
        if JsSyntax.unwrap(url_node).type == 'number':
            return []
        hints = set()
        value = self._module.values.resolve(url_node, hints)
        if value is None or not UrlText.matchable(value):
            return []  # entirely dynamic: nothing to match
        path_like = UrlText.path_like(value)
        if require_path and not path_like:
            return []
        receiver = self._module.receivers.hints(obj) if obj is not None else set()
        if not path_like and (':' in value or Receivers.is_key_value(receiver)):
            return []  # a cache or key-value key ('user:42', 'session'), not a request path
        url = UrlTemplate.split(UrlText.with_params(value))
        if url.path is None:
            return []
        hints.update(url.hints)
        hints.update(JsSyntax.names_in(url_node))
        client = self._client(obj, receiver, hints, relative=not url.hints and '://' not in value)
        return [self._pending(node, method, url.path, hints, client)]

    def _client(self, obj, receiver, hints, relative):
        """The client of a request made on a receiver; its base goes in front of a relative path."""
        if obj is None:
            return None
        hints.add(JsSyntax.text(obj))
        hints.update(receiver)
        return self._module.clients.client(obj, hints) if relative else None

    def _pending(self, node, method, path, hints, client):
        function, owner = Functions.enclosing(node)
        source = self._module.source
        hints.update(h for h in (function, owner, source.path) if h)
        return PendingRequest(
            source,
            JsSyntax.line(node),
            method,
            function,
            frozenset(h[: self.MAX_HINT] for h in hints if h),
            self._workspace.is_test(source, node),
            path,
            client,
        )
