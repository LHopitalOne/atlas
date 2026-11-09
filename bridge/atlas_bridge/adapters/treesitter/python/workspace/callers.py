"""Who calls a function: by name (its own file, and other files for a uniquely named function), or, with a SCIP
index, every call the index resolves to it."""

import re

from ..syntax import PythonSyntax
from ..verbs import HttpVerbs


class CallerIndex:
    """Call sites by called name, read per file on first use, plus which files mention a name at all."""

    CALL_NAME = re.compile(rb'([A-Za-z_]\w*)\(')  # a name directly followed by '(' in raw source: a possible call
    CALLS = '(call) @call'
    # Names too generic to follow into other files: a call to them is rarely a call to this definition.
    STOP = frozenset(HttpVerbs.NAMES) | {'request', 'urlopen', 'send', 'call', 'run', 'main', 'handle'}
    STOP |= {'__init__', '__call__'}
    MAX_SITES = 200

    def __init__(self, sources, definitions, graph=None, repo=''):
        self._sources = sources
        self._definitions = definitions  # function name -> [(source, node)]
        self._graph = graph  # a CallGraph from SCIP indexes, or None
        self._repo = repo
        self._calls = {}  # path -> {callee name: [call nodes]}
        self._mentions = None  # called name -> [sources], built on first use

    def callers_of(self, source, func):
        """[(source, call node)] that call `func`, outside `func` itself, at most MAX_SITES. With an index that knows
        `func`, every call by its name anywhere is a candidate and the index says which really reach it."""
        name = PythonSyntax.name(func)
        key = self._key(source, func, name)
        sites = self._by_name(source, name) if key is None else self._resolved(source, name, key)
        inside = PythonSyntax.FUNCTION
        return [(g, c) for g, c in sites if PythonSyntax.ancestor(c, inside) != func][: self.MAX_SITES]

    def constructions_of(self, source, cls, unique):
        """[(source, call node)] that call the class `cls` by its name: in its own file, and in the other files that
        call that name when the class is the only one so named (`unique`). At most MAX_SITES."""
        name = PythonSyntax.name(cls)
        sites = [(source, c) for c in self._file_calls(source).get(name, ())]
        for other in self._mentioning(name) if unique else ():
            if other is not source:
                sites += [(other, c) for c in self._file_calls(other).get(name, ())]
        return sites[: self.MAX_SITES]

    def _by_name(self, source, name):
        """Calls by name in the same file, and in other files for a uniquely named, not generic function."""
        sites = [(source, c) for c in self._file_calls(source).get(name, ())]
        if name not in self.STOP and self._unique(name):
            for other in self._mentioning(name):
                if other is not source:
                    sites += [(other, c) for c in self._file_calls(other).get(name, ())]
        return sites

    def _key(self, source, func, name):
        """The index's key for `func`, or None when there is no index or it does not know the definition."""
        if self._graph is None:
            return None
        fn = self._graph.enclosing(self._repo, source.path, PythonSyntax.line(func.child_by_field_name('name')))
        return fn.key if fn is not None and fn.name == name else None

    def _resolved(self, source, name, key):
        """Calls by `name` in every file that calls it, kept where the index resolves the name to `key`. A call the
        name-only rule takes stays unless the index says it reaches another library or another function: a method of
        another class may be overridden by this one, so that does not rule it out."""
        plain = {(g.path, c.start_byte) for g, c in self._by_name(source, name)}
        out = []
        for other in [source, *(g for g in self._mentioning(name) if g is not source)]:
            for c in self._file_calls(other).get(name, ()):
                targets = self._graph.resolves(self._repo, other.path, self._name_line(c), name)
                exact = any(t.key == key for t in targets)
                open_ = not targets or any(t.local and t.method for t in targets)
                if exact or ((other.path, c.start_byte) in plain and open_):
                    out.append((other, c))
        return out

    @staticmethod
    def _name_line(call):
        fn = call.child_by_field_name('function')
        return PythonSyntax.line(fn.child_by_field_name('attribute') if fn.type == 'attribute' else fn)

    def _unique(self, name):
        """Exactly one production definition has this name, so a call by name is a call to it."""
        return len([d for d in self._definitions.get(name, []) if not d[0].test]) == 1

    def _file_calls(self, source):
        found = self._calls.get(source.path)
        if found is None:
            found = self._calls[source.path] = {}
            for c in source.captures(self.CALLS).get('call', ()):
                found.setdefault(PythonSyntax.callee(c), []).append(c)
        return found

    def _mentioning(self, name):
        """Files whose source calls `name(` somewhere, from an index built on first use."""
        if self._mentions is None:
            self._mentions = {}
            for source in self._sources:
                for n in set(self.CALL_NAME.findall(source.data)):
                    self._mentions.setdefault(n.decode(), []).append(source)
        return self._mentions.get(name, [])
