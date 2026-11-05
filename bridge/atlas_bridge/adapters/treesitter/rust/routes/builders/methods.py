"""Method routers: which handler serves which HTTP method on one path."""

import re

from ......core.http import ANY
from ....kit import ValueResolver
from ...blocks import Blocks
from ...names import ItemPath
from ...syntax import RustSyntax
from ..actix_attributes import ActixAttributes


class MethodRouters(ValueResolver):
    """resolve(node, file) -> {method: handler} of an axum method router (`get(h).post(g)`, `on(..)`, a factory fn
    returning one) or an actix-web route (`web::post().to(h)`). Anything else serves every method with its text."""

    HANDLERS = {'call_expression': '_call'}

    VERBS = ActixAttributes.VERBS
    MAX_DEPTH = 32  # wrappers around a method router; cycles are caught separately
    FILTER = re.compile(r'MethodFilter::([A-Z]+)')  # axum `on(MethodFilter::GET.or(MethodFilter::POST), h)`
    METHOD = ItemPath.METHOD  # actix `web::method(Method::GET)`
    HANDLER_STEPS = frozenset({'to', 'to_async'})  # actix: the handler of a route built from its method

    def __init__(self, workspace):
        self._workspace = workspace
        self._active = set()  # factory fns being followed: a cycle ends there

    def served(self, file, node) -> dict:
        """{method: handler} of the method router `node` builds."""
        return self.resolve(node, file)

    def resolve(self, node, scope, depth=0):
        return super().resolve(RustSyntax.unwrap(node), scope, depth)

    def unknown(self, node, scope):
        return {ANY: RustSyntax.text(node)}

    def _call(self, node, file, depth):
        args = RustSyntax.args(node)
        first = RustSyntax.text(args[0]) if args else ''
        fn = RustSyntax.method(node)
        if fn is not None:
            return self._chained(file, fn, args, first, depth)
        return self._named(file, node.child_by_field_name('function'), args, first, depth)

    @staticmethod
    def by_handler(served):
        """{method: handler} -> [(handler, methods)]: one route per handler."""
        groups = {}
        for m, h in served.items():
            groups.setdefault(h, set()).add(m)
        return list(groups.items())

    @staticmethod
    def serve(served, methods, handler):
        """Add `methods -> handler` to a method router's map; an unresolved (ANY) receiver is replaced."""
        out = {} if set(served) == {ANY} else dict(served)
        out.update(dict.fromkeys(methods, handler))
        return out

    @classmethod
    def filtered(cls, text):
        """The methods a MethodFilter expression names, in a fixed order, or ANY."""
        return sorted(set(cls.FILTER.findall(text))) or [ANY]

    def _chained(self, file, fn, args, first, depth):
        """`<method router>.name(args)`: adds a method, sets the handler, or wraps (a layer)."""
        name = RustSyntax.text(fn.child_by_field_name('field'))
        served = self.resolve(fn.child_by_field_name('value'), file, depth + 1)
        if name in self.VERBS:
            return self.serve(served, {name.upper()}, first)
        if name == 'on' and len(args) == 2:
            return self.serve(served, self.filtered(first), RustSyntax.text(args[1]))
        if name in self.HANDLER_STEPS and args:  # actix: web::post().to(handler)
            return dict.fromkeys(served, first)
        return served  # a layer or other wrapper

    def _named(self, file, fn, args, first, depth):
        """`name(args)`: get(h), any(h), on(filter, h), web::method(..), or a factory fn in the crate."""
        segs = ItemPath.segments(fn)
        local = segs[-1] if segs else ''
        name = file.imported(local, local).split('::')[-1] if len(segs) == 1 else local
        base = name.removesuffix('_service')
        if base in self.VERBS:
            return {base.upper(): first}
        if base == 'any' or (base == 'route' and not args):
            return {ANY: first}
        if name == 'on' and len(args) == 2:
            return dict.fromkeys(self.filtered(first), RustSyntax.text(args[1]))
        if name == 'method' and args:
            return dict.fromkeys(sorted(set(self.METHOD.findall(first))) or [ANY], '')
        return self._factory(file, fn, segs, depth)

    def _factory(self, file, fn, segs, depth):
        """A crate fn returning a method router: what its return values serve."""
        hit = self._workspace.resolve_fn(file, fn)
        key = hit and hit[0].key(hit[1])
        if hit is None or key in self._active:
            return {ANY: RustSyntax.text(fn)}
        self._active.add(key)
        served = {}
        try:
            cf, target = hit
            for r in Blocks.returns(target):
                for m, h in self.resolve(r, cf, depth + 1).items():
                    served.setdefault(m, h)
        finally:
            self._active.discard(key)
        if not served:
            return {ANY: RustSyntax.text(fn)}
        if len(served) > 1:
            served.pop(ANY, None)
        module = segs[:-1]  # handlers named in a factory live in its module: `store::route` -> `store::handle`
        return {m: '::'.join(module + [h]) if h and module else h or RustSyntax.text(fn) for m, h in served.items()}
