"""Library entry points that send a request named by one of their arguments: data fetching hooks keyed by a URL
(SWR, TanStack Query) and GraphQL clients given a document (Apollo, urql, graphql-request)."""

from dataclasses import dataclass

from .....core.http import Protocol
from ..syntax.nodes import JsSyntax


@dataclass(frozen=True)
class EntryPoint:
    """A function a library exports, and which argument names the channel it sends to.

    libraries: the module names it is imported from; callee: its exported name ('default' for a default export);
    argument: the index of the argument that holds the channel (a URL key, a GraphQL document); option: the property
    of that argument, when it is an options object, that holds it; unless: an option whose presence means a function
    of the caller sends the request instead (TanStack Query's `queryFn`), so the key says nothing.
    """

    SEND = 'send'

    libraries: tuple[str, ...]
    callee: str
    protocol: str
    argument: int = 0
    option: str = ''
    unless: str = ''
    role: str = SEND

    def channel(self, args):
        """The expression among a call's arguments that names the channel, or None."""
        arg = JsSyntax.unwrap(args[self.argument]) if self.argument < len(args) else None
        if arg is None or not self.option:
            return arg
        if arg.type != 'object' or (self.unless and JsSyntax.prop(arg, self.unless) is not None):
            return None
        return JsSyntax.prop(arg, self.option)


SWR = ('swr', 'swr/immutable')
TANSTACK = ('@tanstack/react-query', '@tanstack/vue-query', '@tanstack/solid-query', 'react-query')
APOLLO = ('@apollo/client', '@apollo/client/react', '@apollo/client/react/hooks', '@apollo/react-hooks')
APOLLO_HOOKS = ('useQuery', 'useLazyQuery', 'useSuspenseQuery', 'useBackgroundQuery', 'useMutation', 'useSubscription')
URQL = ('urql', '@urql/preact', '@urql/svelte', '@urql/vue')


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
        # graphql-request: `request(url, document, variables?)`
        EntryPoint(('graphql-request',), 'request', Protocol.GRAPHQL, argument=1),
        EntryPoint(('graphql-request',), 'rawRequest', Protocol.GRAPHQL, argument=1),
    )
    # bytes a file must contain to import one of the libraries (checked before parsing)
    MENTIONS = tuple(sorted({lib.split('/')[0].encode() for e in TABLE for lib in e.libraries}))

    _BY_IMPORT = {(lib, e.callee): e for e in TABLE for lib in e.libraries}

    @classmethod
    def calls_in(cls, module, protocol) -> list:
        """[(call node, entry point)] for the calls of a file to an imported entry point over `protocol`."""
        if not module.source.mentions(*cls.MENTIONS):
            return []
        out = []
        for call in JsSyntax.walk(module.source.root, {'call_expression'}):
            fn = JsSyntax.unwrap(call.child_by_field_name('function'))
            entry = cls.of(module.imports.get(JsSyntax.text(fn)), protocol) if fn.type == 'identifier' else None
            if entry is not None:
                out.append((call, entry))
        return out

    @classmethod
    def of(cls, imported, protocol) -> EntryPoint | None:
        """The entry point a name imported as (module, exported name) is, when it sends over `protocol`."""
        found = cls._BY_IMPORT.get(imported) if imported is not None else None
        return found if found is not None and found.protocol == protocol else None
