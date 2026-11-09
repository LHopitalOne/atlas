"""A request whose URL is made of its function's parameters (`fetch(`${this.baseUrl}${path}`, { method })` inside
`request(method, path)`), followed to the calls that fill them in (`this.request('POST', '/api/rooms')`)."""

import re
from dataclasses import dataclass, replace

from .....core.http import ANY
from ...kit import UrlTemplate
from ..module import JsModule
from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from ..syntax.params import Params
from ..values.urls import UrlText
from .arguments import Arguments
from .callers import Callers
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
    template: str  # the URL, '{name}' where a parameter goes ('{name.key}' where a member of one goes)
    method: str  # 'GET', ANY, or '{name}': the parameter (or option) that holds it ('{a.method|a.type}': either)
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
        if not names & {m[1:-1].split('.')[0] for m in UrlText.PLACEHOLDER.findall(template)}:
            return None
        _, owner = Functions.enclosing(node)
        kind = fn.type == 'method_definition'
        return cls('', Functions.name(fn), owner, kind, params, template, method, method_default, frozenset(hints))


class Forwarder:
    """Settles open requests at the calls of their functions (Callers): a call that fills in a path settles the
    request there; one that passes its own parameters on opens it again one level up. A call that hands the function
    to another one settles it where that function calls the parameter it lands in, with the outer call's arguments.
    A member of an options parameter (`options.url`) is read from the object the caller gives; a `let` assigned
    before the call gives one request per value."""

    MAX_DEPTH = 4  # wrapper levels followed
    MAX_VARIANTS = 8  # requests one call is settled as
    MEMBER_PLACEHOLDER = re.compile(r'\{[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]*)\}')  # '{options.url}' -> 'url'
    UNKNOWN = '{}'  # a value nothing says anything about

    def __init__(self, workspace):
        self._workspace = workspace
        self._modules = {}
        self._arguments = {}
        self._callers = Callers(workspace, self._module)

    def settle(self, opens) -> list[PendingRequest]:
        out, frontier = {}, list(dict.fromkeys(opens))
        seen = set(frontier)
        for _ in range(self.MAX_DEPTH):
            upper = []
            for open_ in frontier:
                upper += self._settle(open_, out)
            frontier = [o for o in dict.fromkeys(upper) if o not in seen]
            seen.update(frontier)
        for module in self._modules.values():
            module.release()
        return list(out.values())

    def _settle(self, open_, out):
        """Settle one open request at its callers (into `out`); the requests opened one level up."""
        direct, handoffs = self._callers.of(open_)
        upper = []
        for module, call in direct:
            upper += self._keep(out, *self._at(open_, module, call))
        for module, handoff in handoffs:
            settled, again = self._at(open_, handoff.module, handoff.inner)
            upper += self._keep(out, settled, [])
            for inner in again:
                if inner.function == handoff.function:  # opened in the receiving function, not one inside it
                    upper += self._keep(out, *self._at(inner, module, handoff.call))
        return upper

    def _keep(self, out, settled, again):
        for p in settled:
            out.setdefault(self._key(p), p)
        return again

    @staticmethod
    def _key(p):
        """What tells two settled requests apart (one call reached through two wrappers is one request)."""
        return p.source.path, p.line, p.method, str(p.path)

    def _module(self, source):
        if source.path not in self._modules:
            self._modules[source.path] = JsModule(source)
        return self._modules[source.path]

    def _args(self, module) -> Arguments:
        if module.path not in self._arguments:
            self._arguments[module.path] = Arguments(module)
        return self._arguments[module.path]

    def _at(self, open_, module, call):
        """([the requests settled at this call], [the requests opened one level up])."""
        hints = set(open_.hints) | {open_.function}
        settled, again = [], []
        envs, fallbacks = self._bind(open_, module, call, hints)
        for env in envs:
            value = self._filled(open_.template, env)
            method, default = self._method(open_, env, fallbacks)
            if UrlText.matchable(value) and UrlText.path_like(value):
                plain = self.MEMBER_PLACEHOLDER.sub(r'{\1}', value)
                settled.append(self._pending(module, call, plain, method, set(hints)))
                continue
            found = OpenRequest.at(call, value, method, default, hints)
            again += [replace(found, path=module.path)] if found is not None else []
        return settled, again

    def _filled(self, template, env):
        for name, v in env.items():
            if v is None:
                v = self.UNKNOWN  # a member the caller leaves out
            if v:
                template = template.replace('{' + name + '}', v)
        return template

    def _bind(self, open_, module, call, hints):
        """([{parameter, option or 'param.key': its value at this call}, one per variant], {'param.key': the value
        it has unless the caller's spread parameter overrides it}). A param's default fills in what the call leaves
        out; a member the caller's object surely leaves out is None."""
        args, read, choices, fallbacks = JsSyntax.args(call), self._args(module), {}, {}
        members = self._members(open_)
        for p in open_.params:
            arg = args[p.index] if p.index < len(args) else None
            if p.name:
                choices[p.name] = tuple(read.resolve(arg, hints)) if arg is not None else (p.default,)
                for key in members.get(p.name, ()):
                    member = read.member(arg, key, hints) if arg is not None else None
                    name = f'{p.name}.{key}'
                    choices[name] = (member.values or (None,)) if member is not None else (self.UNKNOWN,)
                    fallbacks[name] = member.fallback if member is not None else ''
                continue
            for prop, default in p.props:
                node = JsSyntax.prop(arg, prop) if arg is not None else None
                choices[prop] = tuple(read.resolve(node, hints)) if node is not None else (default,)
        envs = [{}]
        for name, values in choices.items():
            envs = [{**e, name: v} for e in envs for v in values][: self.MAX_VARIANTS]
        return envs, fallbacks

    @staticmethod
    def _members(open_):
        """{parameter: [keys]} of the members of parameters the URL or the method is made of."""
        found = {}
        names = [m[1:-1] for m in UrlText.PLACEHOLDER.findall(open_.template)]
        if UrlText.PLACEHOLDER.fullmatch(open_.method):
            names += open_.method[1:-1].split('|')
        for name in names:
            m = Arguments.MEMBER.match(name)
            if m:
                found.setdefault(m.group(1), []).append(m.group(2))
        return found

    def _method(self, open_, env, fallbacks):
        """(the method this call gives, the method when a parameter it is still left to says nothing): a literal,
        or '{name}' again when it passes on a parameter of its own. Of several options that may hold it, the first
        one given wins."""
        if not UrlText.PLACEHOLDER.fullmatch(open_.method):
            return open_.method, open_.method_default
        kept, default = [], open_.method_default
        for name in open_.method[1:-1].split('|'):
            value = env.get(name)
            if not value:
                continue  # left out: the next option, or the default
            if value == self.UNKNOWN:
                return ANY, ''
            if not UrlText.PLACEHOLDER.fullmatch(value):
                if not kept:
                    return (value.upper() if value.isalpha() else ANY), ''
                default = value
                break
            kept.append(value[1:-1])
            default = fallbacks.get(name) or default
        if kept:
            return '{' + '|'.join(kept) + '}', default
        return (default.upper() if default and default.isalpha() else ANY), default

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
