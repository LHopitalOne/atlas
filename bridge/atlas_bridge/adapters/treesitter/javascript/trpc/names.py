"""What tRPC's packages export, and how code that uses them is recognised."""

from ..syntax.nodes import JsSyntax


class TrpcNames:
    """The names of @trpc/server and @trpc/client the readers look for, read through the imports of the file that
    uses them (a local function of the same name is not tRPC's)."""

    SERVER = '@trpc/server'
    CLIENT = '@trpc/client'
    INIT = 'initTRPC'  # initTRPC.create() / initTRPC.context<C>().create() makes the instance `t`
    ROUTER = 'router'  # t.router({...}) makes a router
    # a procedure is a builder chain ending in one of these; subscriptions are not plain HTTP requests
    PROCEDURES = {'query': 'GET', 'mutation': 'POST'}
    CALLS = {'query': 'GET', 'mutate': 'POST'}  # what a vanilla client calls on a procedure, and the method it sends
    CLIENTS = frozenset({'createTRPCClient', 'createTRPCProxyClient'})  # v11, v10
    LINKS = frozenset({'httpLink', 'httpBatchLink', 'httpBatchStreamLink', 'unstable_httpBatchStreamLink'})
    METHOD_OVERRIDE = 'methodOverride'  # a link option that sends queries as POST

    @staticmethod
    def imported(module, node, library, names) -> bool:
        """Whether `node` is a name the file imports from `library` as one of `names`."""
        node = JsSyntax.unwrap(node)
        if node is None or node.type != 'identifier':
            return False
        found = module.imports.get(JsSyntax.text(node))
        return found is not None and found[0] == library and found[1] in names

    @classmethod
    def is_instance(cls, location) -> bool:
        """Whether a written value is the tRPC instance: a call chain on `initTRPC` (`initTRPC.create()`)."""
        node = JsSyntax.unwrap(location.node) if location is not None else None
        if node is None or node.type != 'call_expression':
            return False
        while node is not None and node.type in ('call_expression', 'member_expression'):
            node = JsSyntax.unwrap(node.child_by_field_name('function' if node.type == 'call_expression' else 'object'))
        return cls.imported(location.module, node, cls.SERVER, {cls.INIT})

    @classmethod
    def is_router_factory(cls, location) -> bool:
        """Whether a written value is `t.router` of a tRPC instance `t` (exported as `router` or `createTRPCRouter`)."""
        node = JsSyntax.unwrap(location.node) if location is not None else None
        if node is None or node.type != 'member_expression':
            return False
        if JsSyntax.text(node.child_by_field_name('property')) != cls.ROUTER:
            return False
        return cls.is_instance(location.module.objects.origin(node.child_by_field_name('object')))

    @classmethod
    def is_router(cls, location) -> bool:
        """Whether a written value is a router: a call of a router factory."""
        node = JsSyntax.unwrap(location.node) if location is not None else None
        if node is None or node.type != 'call_expression':
            return False
        return cls.is_router_factory(location.module.objects.origin(node.child_by_field_name('function')))
