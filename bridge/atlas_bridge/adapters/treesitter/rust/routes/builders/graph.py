"""The routers of a crate and how they mount each other: which are roots, which routes each one serves."""

from ....kit import ValueResolver
from ...blocks import Blocks
from ...guard import StackGuard
from ...names import ItemPath
from ...syntax import RustSyntax
from ..found import FoundRoute
from .chain import RouterChain
from .methods import MethodRouters
from .tops import RouterTops


class RouterGraph(ValueResolver):
    """resolve(node, file) -> [FoundRoute]: the routes a router expression yields (`.route` chains, `.nest(prefix,
    r)`, `.merge(r)`, let-bound routers, crate fns returning routers), relative to where it is mounted. A router
    another one nests or merges is consumed; only roots are emitted, so nested routes carry their prefixes. Every
    expression is evaluated once (memoised) and a cycle yields nothing.

    A chain's steps extend the list its base evaluated to, and that list is the base's memo entry, which every
    expression evaluating to the same router shares (a let-bound router and its value, a fn and its callers). So
    two chains built on one router both see the steps of each: the legacy evaluator behaved this way and the
    routes found depend on it. Only this class touches those lists."""

    HANDLERS = {
        'call_expression': '_call',
        'identifier': '_identifier',
        **dict.fromkeys(Blocks.BRANCHING, '_branches'),
    }
    MAX_DEPTH = 32  # nested routers; cycles are caught separately
    BUILDERS = frozenset({'new', 'default'})  # `Router::new()`: an empty router, not a crate fn

    def __init__(self, workspace, attributes):
        self._workspace = workspace
        self._attributes = attributes  # ActixAttributes: a handler named as a router yields its attribute routes
        self._chain = RouterChain(self.resolve, self._mount, MethodRouters(workspace), workspace)
        self._memo, self._active = {}, set()
        self._consumed, self._mounted = set(), set()  # expression keys and fn keys used inside another router
        self._tops = None  # [(file, top call, [FoundRoute])]

    def roots(self) -> list[FoundRoute]:
        """The routes of every router nobody mounts, in source order."""
        out = []
        for f, top, routes in self._evaluated():
            if f.key(top) in self._consumed:
                continue
            fn = RustSyntax.ancestor(top, ('function_item',))
            if fn is not None and f.key(fn) in self._mounted:
                continue
            out += routes
        return out

    def is_mounted(self, fn_key) -> bool:
        """Whether some router uses the fn with this key (`.service(handler)`, `.configure(f)`, a router fn)."""
        self._evaluated()
        return fn_key in self._mounted

    def resolve(self, node, scope, depth=0):
        """The routes of `node` in file `scope`, with the memo, consumed and cycle bookkeeping around dispatch."""
        node = RustSyntax.unwrap(node)
        if node is None or depth > self.MAX_DEPTH:
            return self.unknown(node, scope)
        k = scope.key(node)
        if depth:
            self._consumed.add(k)
        if k in self._memo:
            return self._memo[k]
        if k in self._active:
            return []
        self._active.add(k)
        try:
            out = super().resolve(node, scope, depth)
        finally:
            self._active.discard(k)
        self._memo[k] = out
        return out

    def unknown(self, node, scope):
        return []

    def _mount(self, file, fn):
        """Record that a router uses this fn: its own routers are not roots."""
        self._mounted.add(file.key(fn))

    def _evaluated(self):
        if self._tops is None:
            tops = RouterTops(self._workspace)
            found = [(f, top) for f in self._workspace.files for top in tops.of(f)]
            self._tops = [(f, top, StackGuard.run(self.resolve, top, f)) for f, top in found]
        return self._tops

    def _call(self, node, file, depth):
        if RustSyntax.method(node) is not None:
            return self._chained(node, file, depth)
        return self._called(file, node.child_by_field_name('function'), depth)

    def _chained(self, node, file, depth):
        """A method chain: its base's routes (or an actix scope/resource), extended in place by every step."""
        base, steps = RouterChain.split(node)
        anchor = self._chain.anchor(file, base)
        prefix, resource = anchor if anchor is not None else (None, None)
        routes = [] if anchor is not None else self.resolve(base, file, depth + 1)
        for step in steps:
            routes += self._chain.step(file, step, resource, depth)  # may be a memo entry: see the class docstring
        return [r.under(prefix) for r in routes] if prefix is not None else routes

    def _identifier(self, node, file, depth):
        value = self._workspace.binding(file, node)
        if value is not None:
            return self.resolve(value, file, depth + 1)
        return self._function(file, node, depth, call=False)

    def _branches(self, node, file, depth):
        out = []
        for branch in Blocks.branches(node):
            out += self.resolve(branch, file, depth + 1)
        return out

    def _called(self, file, fn, depth):
        segs = ItemPath.segments(fn) if fn is not None else []
        if not segs or segs[-1] in self.BUILDERS:
            return []
        return self._function(file, fn, depth, call=True)

    def _function(self, file, name_node, depth, call):
        """The routes of a crate fn: its attribute routes when named as a handler, else what it returns."""
        hit = self._workspace.resolve_fn(file, name_node)
        if hit is None:
            return []
        cf, fn = hit
        self._mount(cf, fn)
        attrs = self._attributes.of(cf, fn)
        if attrs and not call:
            handler = RustSyntax.name(fn)
            return [FoundRoute(a.path, a.methods, handler, a.file, a.line) for a in attrs]
        out = []
        for r in Blocks.returns(fn):
            out += self.resolve(r, cf, depth + 1)
        return out
