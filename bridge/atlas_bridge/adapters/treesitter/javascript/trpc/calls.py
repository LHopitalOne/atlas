"""TrpcCalls: the procedures a vanilla tRPC client calls, as HTTP requests to '<link url path>/<dotted path>'."""

from typing import NamedTuple

from .....core.http import Extraction
from ...kit import CallCollector, UrlTemplate
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from .names import TrpcNames


class ClientBase(NamedTuple):
    """Where a client sends: the path of its HTTP link's URL, the hints of that URL, and whether queries go as POST."""

    path: str
    hints: frozenset
    override: bool


class TrpcCalls(CallCollector):
    """`client.notes.create.mutate(input)` on a client made with `createTRPCClient({ links: [httpBatchLink({ url })]
    })` (followed through names and imports to where it is made) is a POST to '<url path>/notes.create'; `.query()` a
    GET (a POST when the link overrides the method). The members between the client and the verb are the procedure's
    path. A client whose links name no HTTP URL, or several, says nothing about where it sends."""

    MAX_HINT = 200
    MENTIONS = tuple(f'.{verb}{c}'.encode() for verb in TrpcNames.CALLS for c in '(<')
    LINKS, URL = 'links', 'url'

    def collect(self) -> Extraction:
        if not any(s.mentions(TrpcNames.CLIENT.encode()) for s in self.workspace.sources):
            return Extraction()
        out, bases = Extraction(), {}
        linker = self.workspace.linker()
        for source in self.workspace.sources:
            if not source.mentions(*self.MENTIONS):
                continue
            module = self.workspace.module(source, linker)
            for call in JsSyntax.walk(source.root, {'call_expression'}):
                out.calls += self._call(module, call, bases)
            module.release()
        linker.release()
        return out

    def _call(self, module, call, bases):
        fn = JsSyntax.unwrap(call.child_by_field_name('function'))
        verb = JsSyntax.text(fn.child_by_field_name('property')) if fn.type == 'member_expression' else ''
        if verb not in TrpcNames.CALLS:
            return []
        names, root = self._chain(fn.child_by_field_name('object'))
        made = module.objects.origin(root) if names and root is not None else None
        base = self._base(made, bases) if made is not None else None
        if base is None:
            return []
        method = 'POST' if base.override else TrpcNames.CALLS[verb]
        function, owner = Functions.enclosing(call)
        hints = base.hints | {h for h in (function, owner, module.path, JsSyntax.text(root)) if h}
        path = f'{base.path.rstrip("/")}/{".".join(names)}'
        test = self.workspace.is_test(module.source, call)
        return [self.call(module.source, JsSyntax.line(call), path, method, function, hints, test)]

    @staticmethod
    def _chain(node):
        """(the property names of a member chain, its root name): `trpc.notes.create` -> (['notes', 'create'],
        `trpc`); ([], None) when the chain does not start at a name."""
        names = []
        node = JsSyntax.unwrap(node)
        while node is not None and node.type == 'member_expression':
            names.append(JsSyntax.text(node.child_by_field_name('property')))
            node = JsSyntax.unwrap(node.child_by_field_name('object'))
        return (names[::-1], node) if node is not None and node.type == 'identifier' else ([], None)

    def _base(self, made, bases):
        """The ClientBase of the client written at `made`, or None when it is not a tRPC client with one HTTP URL."""
        key = (made.module.path, made.node.start_byte, made.node.end_byte)
        if key not in bases:
            bases[key] = self._read_base(made)
        return bases[key]

    def _read_base(self, made):
        node = JsSyntax.unwrap(made.node)
        module = made.module
        if node.type != 'call_expression':
            return None
        if not TrpcNames.imported(module, node.child_by_field_name('function'), TrpcNames.CLIENT, TrpcNames.CLIENTS):
            return None
        args = JsSyntax.args(node)
        options = module.objects.locate(args[0]) if args else None
        given = JsSyntax.prop(options.node, self.LINKS) if options is not None else None
        links = options.module.objects.locate(given) if given is not None else None
        found = self._urls(links) if links is not None else set()
        return found.pop() if len(found) == 1 else None

    def _urls(self, links):
        """The ClientBases of the HTTP links written in a links array (inside splitLink and the like too)."""
        found = set()
        for call in JsSyntax.walk(links.node, {'call_expression'}):
            fn = call.child_by_field_name('function')
            if not TrpcNames.imported(links.module, fn, TrpcNames.CLIENT, TrpcNames.LINKS):
                continue
            args = JsSyntax.args(call)
            url = JsSyntax.prop(args[0], self.URL) if args else None
            hints = set()
            value = links.module.values.resolve(url, hints) if url is not None else None
            split = UrlTemplate.split(value) if value is not None else None
            if split is None or split.path is None:
                return set()  # a link whose URL is not known: where the client sends is not known
            hints |= set(split.hints) | JsSyntax.names_in(url)
            override = JsSyntax.prop(args[0], TrpcNames.METHOD_OVERRIDE) is not None
            found.add(ClientBase(split.path, frozenset(h[: self.MAX_HINT] for h in hints if h), override))
        return found
