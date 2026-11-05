"""Forwarding a request's open parameters from a wrapper function to the call sites that supply them."""

import itertools
from dataclasses import dataclass
from types import MappingProxyType

from .....core.http import ANY
from ..scope import Scope
from ..syntax import PythonSyntax
from ..values import Marker, Value
from ..verbs import HttpVerbs


@dataclass(frozen=True, slots=True, eq=False)
class CallSite:
    """One call of a wrapper function: which argument each parameter gets there (read-only), and whether a `*args`
    leaves the positions unknown."""

    source: object
    call: object
    scope: Scope
    bound: MappingProxyType
    splat: bool

    @classmethod
    def at(cls, source, call, params):
        pos, kw = PythonSyntax.call_args(call)
        bound = {params[i][0]: a for i, a in enumerate(pos[: len(params)]) if a.type != 'dictionary_splat'}
        bound.update(kw)
        splat = any(a.type == 'list_splat' for a in pos)
        return cls(source, call, Scope.at(source, call), MappingProxyType(bound), splat)


class Forwarder:
    """Replaces a wrapper's parameter markers with the values each caller passes, then settles there again."""

    MAX_ALTS = 4  # combinations of argument values tried per call site

    def __init__(self, workspace, settler, values, methods, sites):
        self._workspace = workspace
        self._settler = settler
        self._values = values
        self._methods = methods
        self._sites = sites

    def forward(self, scope, pending, run):
        """Settle `pending` at every call site of the function around `scope`, with that site's arguments."""
        func = scope.func
        wrapper = (scope.source.path, func.start_byte)
        if wrapper in pending.stack or not run.first_visit(pending.visit(wrapper)):
            return  # a cycle, or this function was already forwarded with the same open values
        params = self._params(func)
        defaults = dict(params)
        for source, call in self._workspace.callers.callers_of(scope.source, func):
            site = CallSite.at(source, call, params)
            if site.splat:
                continue
            decided = self._methods.decide(pending.method, func, site.bound, defaults)
            for url, method, hints in self._combinations(scope, site, pending, decided, defaults):
                self._settler.settle(site.scope, call, pending.forwarded(url, method, hints, wrapper), run)

    @staticmethod
    def _params(func):
        """The parameters a caller supplies: a method's `self` or `cls` is left out."""
        params = PythonSyntax.params(func)
        if PythonSyntax.is_method(func) and params and params[0][0] in PythonSyntax.SELF_NAMES:
            return params[1:]
        return params

    def _combinations(self, scope, site, pending, decided, defaults):
        """(url text, method, hints) for each combination of the values the call site gives the open parameters."""
        in_url = Marker.names(pending.url)
        needed = sorted(in_url | Marker.names(decided))
        options = [self._options(scope, site, name, name in in_url, defaults) for name in needed]
        fn = site.call.child_by_field_name('function')
        here = self._sites.hints_for(site.scope, PythonSyntax.receiver(site.call)) | {Value.hint(PythonSyntax.text(fn))}
        for combo in itertools.islice(itertools.product(*options), self.MAX_ALTS):
            url, method, hints = pending.url, decided, set(pending.hints) | here
            for name, v in zip(needed, combo, strict=True):
                url = url.replace(Marker.wrap(name), v.text)
                method = method.replace(Marker.wrap(name), v.text)
                hints |= v.hints
            if not Marker.is_open(method):
                method = HttpVerbs.method(method) or ANY
            yield url, method, frozenset(hints)

    def _options(self, scope, site, name, in_url, defaults):
        """The values a call site gives one parameter: its argument, else the default, else a placeholder."""
        if name in site.bound:
            node, where = site.bound[name], site.scope
        elif defaults.get(name) is not None:
            node, where = defaults[name], scope.without_function()
        else:
            return [Value('{' + name + '}', frozenset(), Value.UNKNOWN)]
        if in_url:
            return self._values.resolve(node, where)
        return [Value(m) for m in self._methods.options(where, node)]
