"""Router method chains: `Router::new().route(..).nest(..)`, actix `web::scope("/p").service(..)`."""

from ......core.http import ANY
from ...names import ItemPath
from ...syntax import RustSyntax
from ..found import FoundRoute
from ..paths import RoutePath


class RouterChain:
    """Reads one method chain: what it starts from and the routes each step adds. It keeps no state: steps that
    mount other routers evaluate them through the graph's `evaluate(node, file, depth)` and report the crate fns
    they mount through `mount(file, fn)`; the graph walks the steps and owns the routes it collects."""

    # (step, number of arguments) -> the method that evaluates it
    STEPS = {
        ('route', 2): '_route',
        ('route_service', 2): '_service',
        ('nest_service', 2): '_service',
        ('nest', 2): '_nest',
        ('merge', 1): '_merge',
        ('service', 1): '_merge',
        ('configure', 1): '_configure',
    }
    BASES = frozenset({'scope', 'resource'})  # actix: a chain on web::scope(p) or web::resource(p)

    def __init__(self, evaluate, mount, methods, workspace):
        self._evaluate = evaluate
        self._mount = mount
        self._methods = methods
        self._workspace = workspace
        self._paths = RoutePath(workspace)

    @staticmethod
    def split(node):
        """(base, [(step name, args, field expression)]) of a chain, steps in the order they apply."""
        steps = []
        while node is not None and node.type == 'call_expression':
            fn = RustSyntax.method(node)
            if fn is None:
                break
            steps.append((RustSyntax.text(fn.child_by_field_name('field')), RustSyntax.args(node), fn))
            node = RustSyntax.unwrap(fn.child_by_field_name('value'))
        steps.reverse()
        return node, steps

    def anchor(self, file, base):
        """(scope prefix, resource path) when the chain starts from actix `web::scope(p)` or `web::resource(p)`
        (either may be None when `p` is not a known string), else None: the base is a router to evaluate."""
        if base is None or base.type != 'call_expression':
            return None
        segs = ItemPath.segments(base.child_by_field_name('function'))
        args = RustSyntax.args(base)
        last = segs[-1] if segs else ''
        if last not in self.BASES or not args:
            return None
        value = self._paths.value(file, args[0])
        return (value, None) if last == 'scope' else (None, value)

    def step(self, file, step, resource, depth) -> list:
        """The routes one step adds to the chain."""
        name, args, fn = step
        return self._step(file, name, args, fn, resource, depth)

    def _step(self, file, name, args, fn, resource, depth):
        ln = RustSyntax.line(fn.child_by_field_name('field'))
        if resource is not None:
            found = self._resource_step(file, name, args, resource, ln)
            if found is not None:
                return found
        method = self.STEPS.get((name, len(args)))
        return getattr(self, method)(file, name, args, ln, depth) if method else []

    def _resource_step(self, file, name, args, resource, ln):
        """actix `web::resource(p).route(r)`, `.to(h)`, `.get(h)`; None for other steps."""
        if name == 'route' and len(args) == 1:
            served = self._methods.served(file, args[0])
            return [FoundRoute(resource, m, h, file, ln) for h, m in self._methods.by_handler(served)]
        if name in self._methods.HANDLER_STEPS and args:
            return [FoundRoute(resource, {ANY}, RustSyntax.text(args[0]), file, ln)]
        if name in self._methods.VERBS and len(args) == 1:
            return [FoundRoute(resource, {name.upper()}, RustSyntax.text(args[0]), file, ln)]
        return None

    def _route(self, file, name, args, ln, depth):
        path = self._paths.value(file, args[0])
        if path is None:
            return []
        served = self._methods.served(file, args[1])
        return [FoundRoute(path, m, h, file, ln) for h, m in self._methods.by_handler(served)]

    def _service(self, file, name, args, ln, depth):
        path = self._paths.value(file, args[0])
        if path is None:
            return []
        path = RoutePath.join(path, '{*rest}') if name == 'nest_service' else path
        return [FoundRoute(path, {ANY}, RustSyntax.text(args[1]), file, ln)]

    def _nest(self, file, name, args, ln, depth):
        prefix = self._paths.value(file, args[0])
        if prefix is None:
            return []
        return [r.under(prefix) for r in self._evaluate(args[1], file, depth + 1)]

    def _merge(self, file, name, args, ln, depth):
        return self._evaluate(args[0], file, depth + 1)

    def _configure(self, file, name, args, ln, depth):
        """actix `.configure(f)`: the routers built by the statements of `fn f(cfg)`."""
        hit = self._workspace.resolve_fn(file, RustSyntax.unwrap(args[0]))
        if hit is None:
            return []
        cf, fn = hit
        self._mount(cf, fn)
        out = []
        body = fn.child_by_field_name('body')
        for st in body.named_children if body is not None else []:
            if st.type == 'expression_statement' and st.named_children:
                out += self._evaluate(st.named_children[0], cf, depth + 1)
        return out
