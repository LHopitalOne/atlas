"""Call sites: the calls whose callee has one of the names routes and requests are made with."""

from .nodes import JsSyntax


class CallSite:
    """`fetch(url)`, `app.get('/p', h)`, `api.request(config)`: a call node, its callee name, arguments and receiver."""

    VERBS = ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')
    ROUTE_VERBS = (*VERBS, 'all', 'del')
    REQUEST_METHODS = ('request', 'requestPromise')
    DIRECT = ('fetch', 'axios', 'got', 'ky')  # functions that send a request when called
    GLOBALS = ('window', 'globalThis', 'self', 'global')  # `window.fetch(...)` is `fetch(...)`
    NAMES = (*ROUTE_VERBS, *REQUEST_METHODS, *DIRECT, 'route', 'use')
    QUERY = (
        '(call_expression function: [(identifier) @name (member_expression property: (property_identifier) @name)] '
        '(#any-of? @name ' + ' '.join(f'"{n}"' for n in NAMES) + ')) @call'
    )

    def __init__(self, node, name):
        self._node = node
        self._name = name
        function = node.child_by_field_name('function')
        self._member = function.type != 'identifier'
        self._receiver = JsSyntax.unwrap(function.child_by_field_name('object')) if self._member else None
        self._args = JsSyntax.args(node)

    @staticmethod
    def method_of(verb):
        """The HTTP method a verb names: 'get' -> 'GET', 'del' -> 'DELETE'."""
        return 'DELETE' if verb.lower() == 'del' else verb.upper()

    @classmethod
    def all_in(cls, source):
        """Every call site of a source file, in source order."""
        return [cls(caps['call'][0], JsSyntax.text(caps['name'][0])) for _, caps in source.matches(cls.QUERY)]

    @property
    def node(self):
        return self._node

    @property
    def name(self):
        return self._name

    @property
    def is_member(self):
        """`x.name(...)` rather than `name(...)`."""
        return self._member

    @property
    def receiver(self):
        """The object a member call is made on (`app` in `app.get(...)`), without casts; None for a plain call."""
        return self._receiver

    @property
    def args(self):
        return self._args

    def on_global(self):
        """`window.fetch(...)`, `globalThis.fetch(...)`: the global function, called through the global object."""
        return self._member and JsSyntax.text(self._receiver) in self.GLOBALS
