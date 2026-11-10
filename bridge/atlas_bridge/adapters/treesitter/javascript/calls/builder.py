"""Turning the URL argument of a request call into a PendingRequest: its path, hints, client and test flag."""

from dataclasses import replace

from .....core.http import ANY
from ...kit import UrlTemplate
from ..bindings.receivers import Receivers
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..values.assignments import Assignments
from ..values.urls import UrlText
from .arguments import ParamValues
from .forwarding import OpenRequest
from .pending import PendingRequest


class RequestBuilder:
    """Builds the requests of one file."""

    MAX_HINT = 200  # longer hints are cut
    NAMES = frozenset({'identifier', 'shorthand_property_identifier'})  # `{ method }`, `{ method: m }`
    METHOD_KEYS = ('method',)  # the options that hold the method (jQuery also reads `type`)
    URL_KEY = 'url'

    def __init__(self, workspace, module):
        self._workspace = workspace
        self._module = module
        self._params = None  # ParamValues of the file, made when a request is opened
        self._assignments = Assignments()
        self.opens = []  # OpenRequest: URLs made of their function's parameters, settled at its callers later

    @property
    def module(self):
        return self._module

    def method(self, options, default, keys=METHOD_KEYS):
        """The `method` of a request options object (literal, or a const bound to one); ANY when not a literal."""
        options = self._object(options)
        if options is None:
            return default
        method = self._given(options, keys)
        if method is None:
            return default
        method = JsSyntax.unwrap(method)
        if method.type == 'string':
            return (JsSyntax.string(method) or default).upper()
        return ANY

    def from_config(self, node, obj, config):
        """`axios({url, method})`, `api.request({url})`."""
        url = JsSyntax.prop(config, self.URL_KEY)
        if url is None:
            return []
        return self.build(node, obj, url, self.method(config, 'GET'))

    def from_settings(self, node, settings, default, keys, require_path=False):
        """A request given one settings object (`$.ajax(settings)`): an object literal, a const bound to one, or a
        parameter whose `url` and method the function's callers give (kept as an open request)."""
        settings = JsSyntax.unwrap(settings)
        if settings is not None and settings.type == 'identifier' and self.params.is_parameter(settings):
            name = JsSyntax.text(settings)
            method = '{' + '|'.join(f'{name}.{k}' for k in keys) + '}'
            self._keep(OpenRequest.at(node, '{' + name + '.' + self.URL_KEY + '}', method, default, {name}))
            return []
        settings = self._object(settings)
        url = JsSyntax.prop(settings, self.URL_KEY) if settings is not None else None
        if url is None:
            return []
        method = self.method(settings, default, keys)
        return self.build(node, None, url, method, require_path, options=settings, method_keys=keys)

    @property
    def params(self) -> ParamValues:
        if self._params is None:
            self._params = ParamValues(self._module)
        return self._params

    def build(self, node, obj, url_node, method, require_path=False, options=None, method_keys=METHOD_KEYS):
        """[the request] when `url_node` holds something to match a route with, one per value a `let` is assigned
        before it is read; [] when it does not (a URL made of the function's parameters is kept as an open request,
        for its callers to fill in)."""
        if JsSyntax.unwrap(url_node).type == 'number':
            return []
        out = []
        for value_node in self._assignments.values(url_node):
            out += self._build(node, obj, value_node, method, require_path, (options, method_keys))
        return out

    def _build(self, node, obj, url_node, method, require_path, given):
        hints = set()
        value = self._module.values.resolve(url_node, hints)
        unknown_path = value is not None and UrlText.unknown_path(value)  # 'https://host/{*path}'
        if value is None or unknown_path or not UrlText.matchable(value):
            if value is not None and obj is None:
                value = self.params.resolve(url_node, hints)  # a parameter's member stays '{param.key}'
                value = UrlText.untailed(value) if unknown_path else value  # the path is the callers'
                self._open(node, value, method, given, hints, url_node)
            return []  # entirely dynamic here: nothing to match
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

    def _open(self, node, value, method, given, hints, url_node=None):
        """Keep a URL made of the enclosing function's parameters; `{ method }` from a parameter is filled in too."""
        options, keys = given
        given = self._given(options, keys) if options is not None else None
        if method == ANY and given is not None and JsSyntax.unwrap(given).type in self.NAMES:
            method = '{' + JsSyntax.text(given) + '}'
        found = OpenRequest.at(node, value, method, '', hints)
        if found is None and url_node is not None:
            found = OpenRequest.at_constructor(node, url_node, value, method, '', hints)
        self._keep(found)

    def _keep(self, found):
        if found is not None:
            self.opens.append(replace(found, path=self._module.path))

    def _object(self, options):
        """The object literal of request options (written there, or a const bound to one), or None."""
        options = JsSyntax.unwrap(options)
        if options is not None and options.type == 'identifier':
            options = JsSyntax.unwrap(self._module.scopes.lookup(options, JsSyntax.text(options)))
        return options if options is not None and options.type == 'object' else None

    @staticmethod
    def _given(options, keys):
        """The first of the option keys an options object gives a value, or None."""
        return next((v for v in (JsSyntax.prop(options, k) for k in keys) if v is not None), None)

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
