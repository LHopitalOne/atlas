"""The module an include() names: a dotted path written as a string, an f-string or a constant."""

from ...syntax import PythonSyntax
from ...values import Marker


class IncludedModules:
    """`include('app.urls')`, `include(URLS)` with `URLS = 'app.urls'`, `include(f'{APP}.urls')` with APP a constant,
    and `include(f'{app}.urls')` in a module-level `for app in [...]` loop (the loop's text for the variable).
    A path that does not resolve to one literal names no module."""

    INTERPOLATION = 'interpolation'

    def __init__(self, names, values):
        self._names = names  # NameLookup
        self._values = values

    def module(self, scope, node, given):
        """The file of the module `node` names, read in `scope` with `given` {loop variable: text}; or None."""
        text = self._formatted(scope, node, given) if given and node.type == 'string' else self._literal(scope, node)
        return self._names.dotted_module(text) if text else None

    def _literal(self, scope, node):
        found = self._values.resolve(node, scope)
        v = found[0] if len(found) == 1 else None
        return v.text if v is not None and v.is_literal and not Marker.names(v.text) and '{' not in v.text else None

    def _formatted(self, scope, node, given):
        """An f-string's text with the loop's variables filled in and its other names read as constants."""
        out = []
        for c in node.children:
            if c.type == 'string_content':
                out.append(PythonSyntax.text(c))
            elif c.type == self.INTERPOLATION:
                expr = c.named_children[0] if c.named_children else None
                name = PythonSyntax.text(expr) if expr is not None else ''
                text = given.get(name) if expr is not None and expr.type == 'identifier' else None
                text = text if text is not None else (self._literal(scope, expr) if expr is not None else None)
                if text is None:
                    return None
                out.append(text)
        return ''.join(out)
