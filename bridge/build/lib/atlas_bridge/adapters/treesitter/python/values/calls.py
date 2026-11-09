"""Handlers for the calls that build URLs: `.format`, `'/'.join([...])`, `urljoin`, `os.path.join`, `.strip()` and
friends, `str(x)` and `cast(T, x)`."""

from ..syntax import PythonSyntax
from .formatting import FormatCall
from .value import Value


class CallHandlers:
    """Mixed into a ScopeResolver that also reads strings and helper calls (HelperHandlers): a call that builds a URL
    resolves to what it builds, a call of a helper that returns one to what it returns, any other call is unknown."""

    HANDLERS = {'call': 'call'}
    JOINS = frozenset({'urljoin', 'url_join'})
    PATH_JOINS = frozenset({'posixpath', 'os.path', 'path'})
    STRIPS = frozenset({'rstrip', 'lstrip', 'strip'})
    CONVERSIONS = frozenset({'str', 'cast'})

    def call(self, node, scope, depth):
        found = self._call_value(node, scope, depth) or self.helper_value(node, scope, depth)
        return found if found else self.unknown(node)

    def _call_value(self, node, scope, depth):
        fn = node.child_by_field_name('function')
        pos, kw = PythonSyntax.call_args(node)
        if fn.type == 'attribute':
            return self._method_call(fn, pos, kw, scope, depth)
        if fn.type == 'identifier':
            name = PythonSyntax.text(fn)
            if name in self.JOINS:
                return self._urljoin(pos, scope, depth)
            if name in self.CONVERSIONS and pos:
                return self.resolve(pos[-1], scope, depth + 1)
        return None

    def _method_call(self, fn, pos, kw, scope, depth):
        attr = PythonSyntax.text(fn.child_by_field_name('attribute'))
        obj = fn.child_by_field_name('object')
        if attr == 'format':
            return self._format(obj, FormatCall(self, scope, pos, kw, depth), scope, depth)
        if attr == 'join' and obj.type == 'string' and pos and pos[0].type in ('list', 'tuple'):
            return self._str_join(obj, pos[0], scope, depth)
        if attr in self.JOINS or (attr == 'join' and PythonSyntax.text(obj) in self.PATH_JOINS):
            return self._urljoin(pos, scope, depth)
        if attr in self.STRIPS:
            return self.resolve(obj, scope, depth + 1)
        return None

    def _str_join(self, separator, items, scope, depth):
        sep = self.string(separator, scope, depth).text
        acc = [Value('', frozenset(), Value.LITERAL)]
        for i, item in enumerate(items.named_children):
            part = self.resolve(item, scope, depth + 1)
            acc = self.join(acc, part if i == 0 else self.join([Value(sep)], part))
        return acc

    def _urljoin(self, pos, scope, depth):
        if not pos:
            return None
        acc = self.resolve(pos[0], scope, depth + 1)
        if all(v.is_unknown for v in acc):
            hints = frozenset().union(*(v.hints for v in acc)) | {Value.hint(PythonSyntax.text(pos[0]))}
            acc = [Value('{}', hints, Value.LITERAL)]
        for p in pos[1:]:
            acc = self.join(self.join(acc, [Value('/')]), self.resolve(p, scope, depth + 1))
        return acc

    def _format(self, template, call, scope, depth):
        out = []
        for v in self.resolve(template, scope, depth + 1):
            if v.is_literal:
                formatted = call.apply(v)
                if formatted is not None:
                    out.append(formatted)
        return out
