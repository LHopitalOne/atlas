"""A request whose URL is made of its function's parameters (`fetch(`${this.baseUrl}${path}`, { method })` inside
`request(method, path)`), followed to the calls that fill them in (`this.request('POST', '/api/rooms')`)."""

from dataclasses import dataclass, replace

from .....core.http import ANY
from ...kit import UrlTemplate
from ..module import JsModule
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..syntax.params import Params
from ..values.urls import UrlText
from .pending import PendingRequest


@dataclass(frozen=True)
class OpenRequest:
    """A request read inside a function, still waiting for its callers' arguments. Plain data only: the file's
    syntax tree is released once the file is read."""

    path: str  # the file of the function
    function: str
    owner: str  # the class of a method
    method_of_class: bool
    params: tuple  # syntax.params.Param
    template: str  # the URL, '{name}' where a parameter goes
    method: str  # 'GET', ANY, or '{name}': the parameter (or option) that holds it
    method_default: str
    hints: frozenset

    @classmethod
    def at(cls, node, template, method, method_default, hints):
        """The open request of a URL inside a function whose parameters it uses; None when it uses none."""
        fn = Functions.named_ancestor(node)
        if fn is None:
            return None
        params = Params.of(fn)
        names = {n for p in params for n in p.names}
        if not names & {m[1:-1] for m in UrlText.PLACEHOLDER.findall(template)}:
            return None
        _, owner = Functions.enclosing(node)
        kind = fn.type == 'method_definition'
        return cls('', Functions.name(fn), owner, kind, params, template, method, method_default, frozenset(hints))


class Forwarder:
    """Settles open requests at the calls of their functions: a function by name in its file and in the files that
    import it, a method through `this` in its class. A call that fills in a path settles the request there; one that
    passes its own parameters on opens it again one level up."""

    MAX_DEPTH = 3  # wrapper levels followed
    MAX_SITES = 200  # calls one open request is settled at

    def __init__(self, workspace):
        self._workspace = workspace
        self._modules = {}

    def settle(self, opens) -> list[PendingRequest]:
        out, frontier = [], list(opens)
        for _ in range(self.MAX_DEPTH):
            upper = []
            for open_ in frontier:
                for module, call in self._callers(open_)[: self.MAX_SITES]:
                    settled, again = self._at(open_, module, call)
                    out += settled
                    upper += again
            frontier = upper
        for module in self._modules.values():
            module.release()
        return out

    def _callers(self, open_):
        found = []
        for source in self._workspace.sources:
            if not source.mentions(open_.function.encode()):
                continue
            module = self._module(source)
            if open_.method_of_class and module.path != open_.path:
                continue
            if not open_.method_of_class and module.path != open_.path and module.imports.get(open_.function) is None:
                continue
            found += [(module, c) for c in JsSyntax.walk(source.root, {'call_expression'}) if self._calls(open_, c)]
        return found

    @staticmethod
    def _calls(open_, call):
        fn = JsSyntax.unwrap(call.child_by_field_name('function'))
        if open_.method_of_class:
            ok = fn.type == 'member_expression' and JsSyntax.text(fn.child_by_field_name('object')) == 'this'
            ok = ok and JsSyntax.text(fn.child_by_field_name('property')) == open_.function
            return ok and Functions.enclosing(call)[1] == open_.owner
        return fn.type == 'identifier' and JsSyntax.text(fn) == open_.function

    def _module(self, source):
        if source.path not in self._modules:
            self._modules[source.path] = JsModule(source)
        return self._modules[source.path]

    def _at(self, open_, module, call):
        """([the request settled at this call], [the request opened one level up])."""
        hints = set(open_.hints) | {open_.function}
        env = self._bind(open_, module, call, hints)
        value = open_.template
        for name, v in env.items():
            if v:
                value = value.replace('{' + name + '}', v)
        method = self._method(open_, env)
        if UrlText.matchable(value) and UrlText.path_like(value):
            return [self._pending(module, call, value, method, hints)], []
        again = OpenRequest.at(call, value, method, open_.method_default, hints)
        return [], [replace(again, path=module.path)] if again is not None else []

    @staticmethod
    def _bind(open_, module, call, hints):
        """{parameter or option name: its value at this call} (a param's default when the call leaves it out)."""
        args, env = JsSyntax.args(call), {}
        for p in open_.params:
            arg = args[p.index] if p.index < len(args) else None
            if p.name:
                env[p.name] = module.values.resolve(arg, hints) if arg is not None else p.default
                continue
            for prop, default in p.props:
                node = JsSyntax.prop(arg, prop) if arg is not None else None
                env[prop] = module.values.resolve(node, hints) if node is not None else default
        return env

    @staticmethod
    def _method(open_, env):
        """The method this call gives: a literal, or '{name}' again when it passes on a parameter of its own."""
        if not UrlText.PLACEHOLDER.fullmatch(open_.method):
            return open_.method
        value = env.get(open_.method[1:-1]) or open_.method_default
        if value and UrlText.PLACEHOLDER.fullmatch(value):
            return value
        return value.upper() if value and value.isalpha() else ANY

    def _pending(self, module, call, value, method, hints):
        url = UrlTemplate.split(UrlText.with_params(value))
        hints.update(url.hints)
        function, owner = Functions.enclosing(call)
        hints.update(h for h in (function, owner, module.path) if h)
        test = self._workspace.is_test(module.source, call)
        method = ANY if UrlText.PLACEHOLDER.fullmatch(method) else method  # still a parameter at the last level
        return PendingRequest(
            module.source, JsSyntax.line(call), method, function, frozenset(hints), test, url.path, None
        )
