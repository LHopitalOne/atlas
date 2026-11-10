"""Library entry points that send a request named by one of their arguments: data fetching hooks keyed by a URL
(SWR, TanStack Query) and GraphQL clients given a document (Apollo, urql, graphql-request), as functions or as
methods of a client object the library's class makes."""

from dataclasses import dataclass

from .....core.http import Protocol
from ..syntax.nodes import JsSyntax


@dataclass(frozen=True)
class EntryPoint:
    """A function a library exports, and which argument names the channel it sends to.

    libraries: the module names it is imported from; callee: its exported name ('default' for a default export);
    argument: the index of the argument that holds the channel (a URL key, a GraphQL document); option: the property
    of that argument, when it is an options object, that holds it; unless: an option whose presence means a function
    of the caller sends the request instead (TanStack Query's `queryFn`), so the key says nothing. An options object
    that spreads another (`{ ...options, queryKey }`) may hold that option unseen, so it says nothing either.
    positional: with an option, the argument names the channel itself when it is not an options object. made_by: the
    class the library exports whose instances have this method (`new GraphQLClient(url).request(document)`); ''
    for a function.
    """

    SPREAD = 'spread_element'

    SEND = 'send'

    libraries: tuple[str, ...]
    callee: str
    protocol: str
    argument: int = 0
    option: str = ''
    unless: str = ''
    role: str = SEND
    positional: bool = False
    made_by: str = ''

    def channel(self, args):
        """The expression among a call's arguments that names the channel, or None."""
        arg = JsSyntax.unwrap(args[self.argument]) if self.argument < len(args) else None
        if arg is None or not self.option:
            return arg
        if arg.type != 'object':
            return arg if self.positional else None
        if self.unless and (
            JsSyntax.prop(arg, self.unless) is not None or any(c.type == self.SPREAD for c in arg.named_children)
        ):
            return None
        return JsSyntax.prop(arg, self.option)


SWR = ('swr', 'swr/immutable')
TANSTACK = ('@tanstack/react-query', '@tanstack/vue-query', '@tanstack/solid-query', 'react-query')
APOLLO = ('@apollo/client', '@apollo/client/react', '@apollo/client/react/hooks', '@apollo/react-hooks')
APOLLO_HOOKS = ('useQuery', 'useLazyQuery', 'useSuspenseQuery', 'useBackgroundQuery', 'useMutation', 'useSubscription')
URQL = ('urql', '@urql/preact', '@urql/vue')  # @urql/svelte has stores (queryStore), not these hooks
GRAPHQL_REQUEST = ('graphql-request',)


class EntryPoints:
    """The table, and lookups by the import a called name comes from."""

    TABLE = (
        # SWR: `useSWR(key, fetcher?, options?)` fetches the key (with the fetcher given, or the SWRConfig one)
        EntryPoint(SWR, 'default', Protocol.HTTP),
        EntryPoint(SWR[:1], 'preload', Protocol.HTTP),
        # TanStack Query: `useQuery({ queryKey })` with the client's default queryFn fetches the key
        EntryPoint(TANSTACK, 'useQuery', Protocol.HTTP, option='queryKey', unless='queryFn'),
        EntryPoint(TANSTACK, 'useSuspenseQuery', Protocol.HTTP, option='queryKey', unless='queryFn'),
        # Apollo Client hooks take the document first: `useQuery(GET_ROOMS, { variables })`
        *(EntryPoint(APOLLO, hook, Protocol.GRAPHQL) for hook in APOLLO_HOOKS),
        # urql: `useQuery({ query })`, `useSubscription({ query })`, `useMutation(document)`
        EntryPoint(URQL, 'useQuery', Protocol.GRAPHQL, option='query'),
        EntryPoint(URQL, 'useSubscription', Protocol.GRAPHQL, option='query'),
        EntryPoint(URQL, 'useMutation', Protocol.GRAPHQL),
        # Apollo Client's own methods: `client.query({ query })`, `client.mutate({ mutation })`
        EntryPoint(APOLLO[:1], 'query', Protocol.GRAPHQL, option='query', made_by='ApolloClient'),
        EntryPoint(APOLLO[:1], 'mutate', Protocol.GRAPHQL, option='mutation', made_by='ApolloClient'),
        EntryPoint(APOLLO[:1], 'subscribe', Protocol.GRAPHQL, option='query', made_by='ApolloClient'),
        # graphql-request: `request(url, document, variables?)`; a client made with `new GraphQLClient(url)` takes the
        # document first or as an option: `client.request(document, variables?)`, `client.request({ document })`
        EntryPoint(GRAPHQL_REQUEST, 'request', Protocol.GRAPHQL, argument=1),
        EntryPoint(GRAPHQL_REQUEST, 'rawRequest', Protocol.GRAPHQL, argument=1),
        EntryPoint(
            GRAPHQL_REQUEST, 'request', Protocol.GRAPHQL, option='document', positional=True, made_by='GraphQLClient'
        ),
        EntryPoint(
            GRAPHQL_REQUEST, 'rawRequest', Protocol.GRAPHQL, option='query', positional=True, made_by='GraphQLClient'
        ),
    )
    # bytes a file must contain to import one of the libraries (checked before parsing)
    MENTIONS = tuple(sorted({lib.split('/')[0].encode() for e in TABLE for lib in e.libraries}))

    _BY_IMPORT = {(lib, e.callee): e for e in TABLE for lib in e.libraries if not e.made_by}
    METHODS = frozenset(e.callee for e in TABLE if e.made_by)  # the methods of client objects in the table
    # bytes a file must contain to call one of them on a client, which it may import from another file of its own
    METHOD_MENTIONS = tuple(sorted(f'.{m}{c}'.encode() for m in METHODS for c in '(<'))

    @classmethod
    def calls_in(cls, module, protocol) -> list:
        """[(call node, entry point)] for the calls of a file to an imported entry point over `protocol`, and to a
        method of a client object one makes."""
        functions, methods = module.source.mentions(*cls.MENTIONS), module.source.mentions(*cls.METHOD_MENTIONS)
        if not functions and not methods:
            return []
        out = []
        for call in JsSyntax.walk(module.source.root, {'call_expression'}):
            fn = JsSyntax.unwrap(call.child_by_field_name('function'))
            if fn.type == 'identifier' and not functions:
                continue
            if fn.type == 'identifier':
                entry = cls.of(module.imports.get(JsSyntax.text(fn)), protocol)
            else:
                entry = cls.method(module, fn, protocol) if fn.type == 'member_expression' else None
            if entry is not None:
                out.append((call, entry))
        return out

    @classmethod
    def method(cls, module, fn, protocol) -> EntryPoint | None:
        """The entry point a method call (`client.request`) is, when its receiver is an object the entry's class
        makes: written where it is made, or followed there through bindings and imports (`new GraphQLClient(url)`)."""
        name = JsSyntax.text(fn.child_by_field_name('property'))
        if name not in cls.METHODS:
            return None
        entries = [e for e in cls.TABLE if e.made_by and e.callee == name and e.protocol == protocol]
        made = module.objects.locate(fn.child_by_field_name('object')) if entries else None
        node = JsSyntax.unwrap(made.node) if made is not None else None
        if node is None or node.type != 'new_expression':
            return None
        ctor = JsSyntax.unwrap(node.child_by_field_name('constructor'))
        imported = made.module.imports.get(JsSyntax.text(ctor)) if ctor.type == 'identifier' else None
        return next((e for e in entries if imported in [(lib, e.made_by) for lib in e.libraries]), None)

    @classmethod
    def of(cls, imported, protocol) -> EntryPoint | None:
        """The entry point a name imported as (module, exported name) is, when it sends over `protocol`."""
        found = cls._BY_IMPORT.get(imported) if imported is not None else None
        return found if found is not None and found.protocol == protocol else None
