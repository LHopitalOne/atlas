"""Who calls a function: its call sites in its own file and, for a uniquely named function, in other files."""

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

    def __init__(self, sources, definitions):
        self._sources = sources
        self._definitions = definitions  # function name -> [(source, node)]
        self._calls = {}  # path -> {callee name: [call nodes]}
        self._mentions = None  # called name -> [sources], built on first use

    def callers_of(self, source, func):
        """[(source, call node)] that call `func`, outside `func` itself, at most MAX_SITES."""
        name = PythonSyntax.name(func)
        sites = [(source, c) for c in self._file_calls(source).get(name, ())]
        if name not in self.STOP and self._unique(name):
            for other in self._mentioning(name):
                if other is not source:
                    sites += [(other, c) for c in self._file_calls(other).get(name, ())]
        inside = PythonSyntax.FUNCTION
        return [(g, c) for g, c in sites if PythonSyntax.ancestor(c, inside) != func][: self.MAX_SITES]

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
