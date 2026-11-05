"""`let` bindings: what a name holds at a point in its function."""

import bisect

from .syntax import RustSyntax


class LetBindings:
    """Finds the `let` a name refers to. Each function's lets are indexed once, by name, in source order."""

    def __init__(self):
        self._functions = {}  # function key -> {name: ([let start], [(let node, enclosing block)])}

    def value(self, file, node):
        """The value of the latest `let name = value` before `node` in its function, or None."""
        scope = RustSyntax.ancestor(node, ('function_item',))
        if scope is None:
            return None
        starts, lets = self._lets(file, scope).get(RustSyntax.text(node), ((), ()))
        pos = node.start_byte
        for i in range(bisect.bisect_left(starts, pos) - 1, -1, -1):
            let, block = lets[i]
            if let.end_byte <= pos and block.start_byte <= pos <= block.end_byte:  # in scope at `node`
                return let.child_by_field_name('value')
        return None

    def _lets(self, file, scope):
        k = file.key(scope)
        if k not in self._functions:
            index = {}
            for name, lets in self._find(scope).items():
                lets.sort(key=lambda e: e[0].start_byte)
                index[name] = ([let.start_byte for let, _ in lets], lets)
            self._functions[k] = index
        return self._functions[k]

    @staticmethod
    def _find(scope):
        """{name: [(let declaration, enclosing block)]} of a function, not looking into nested functions."""
        found = {}
        stack = [scope.child_by_field_name('body')]
        while stack:
            n = stack.pop()
            for c in n.named_children if n is not None else ():
                pat, value = c.child_by_field_name('pattern'), c.child_by_field_name('value')
                if c.type == 'let_declaration' and pat is not None and value is not None:
                    found.setdefault(RustSyntax.text(pat).replace('mut ', '').strip(), []).append((c, n))
                if c.type != 'function_item':
                    stack.append(c)
        return found
