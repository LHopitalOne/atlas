"""GraphQL over HTTP: a request whose JSON body carries `{ query, variables }` (the GraphQL-over-HTTP convention)."""

from ...syntax.nodes import JsSyntax
from ...syntax.site import CallSite
from .document import GraphqlDocument
from .text import DocumentText


class GraphqlBody:
    """Finds the document of a request that posts `{ query }`: `fetch(url, { body: JSON.stringify({ query }) })`,
    `axios.post(url, { query })`, `axios({ url, data: { query } })`, `ky.post(url, { json: { query } })`.

    The request sends GraphQL when that document reads as one (`query Rooms { rooms { id } }`), or when it is a
    parameter of the enclosing function (a `gql(query, variables)` helper, whose callers give the document) and the
    URL names a GraphQL endpoint. A `{ query: searchText }` body sends nothing of the kind.
    """

    VERBS = frozenset({'post', 'put', 'patch'})  # client methods whose second argument is the body
    NAMES = frozenset({*CallSite.DIRECT, *VERBS, *CallSite.REQUEST_METHODS})  # calls that send a body
    BODY_KEYS = ('body', 'data', 'json')  # fetch / axios / ky and got
    CONFIG_KEYS = ('data', 'body')  # `axios({ url, data })`, `api.request({ url, body })`
    QUERY = 'query'
    URL = 'url'
    STRINGIFY = 'JSON.stringify'
    ENDPOINT = 'graphql'  # a word of the endpoint's URL by convention ('/graphql', '/api/graphql')

    @classmethod
    def document(cls, module, site: CallSite):
        """The `query` member of the request's JSON body, or None."""
        candidates = [site.args[1]] if site.name in cls.VERBS and len(site.args) > 1 else []  # `post(url, data)`
        for arg in site.args[1:]:
            candidates += [JsSyntax.prop(arg, k) for k in cls.BODY_KEYS]
        if site.args:
            candidates += [JsSyntax.prop(site.args[0], k) for k in cls.CONFIG_KEYS]
        for candidate in candidates:
            body = cls._object(module, candidate)
            query = JsSyntax.prop(body, cls.QUERY) if body is not None else None
            if query is not None:
                return query
        return None

    @classmethod
    def url(cls, site: CallSite):
        """The URL argument of the request (the `url` of a config object)."""
        first = JsSyntax.unwrap(site.args[0]) if site.args else None
        if first is not None and first.type == 'object':
            return JsSyntax.prop(first, cls.URL)
        return first

    @classmethod
    def sends_graphql(cls, module, site: CallSite) -> bool:
        """The request posts a GraphQL document (see the class docstring)."""
        query = cls.document(module, site)
        if query is None:
            return False
        if GraphqlDocument(DocumentText.of(module, query) or '').operations():
            return True
        url = cls.url(site)
        named = url is not None and cls.ENDPOINT in module.values.resolve(url, set()).lower()
        return named and DocumentText.parameter(module, query) is not None

    @classmethod
    def _object(cls, module, node):
        """The object literal a body expression is (through a const and `JSON.stringify`), or None."""
        for _ in range(3):
            node = JsSyntax.unwrap(node)
            if node is None:
                return None
            if node.type == 'object':
                return node
            if node.type in ('identifier', 'shorthand_property_identifier'):
                node = module.scopes.lookup(node, JsSyntax.text(node))
            elif (
                node.type == 'call_expression' and JsSyntax.text(node.child_by_field_name('function')) == cls.STRINGIFY
            ):
                args = JsSyntax.args(node)
                node = args[0] if args else None
            else:
                return None
        return None
