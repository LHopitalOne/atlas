"""The module an include() names: a dotted path written as a string, an f-string or a constant."""

from .loops import BoundText


class IncludedModules:
    """`include('app.urls')`, `include(URLS)` with `URLS = 'app.urls'`, `include(f'{APP}.urls')` with APP a constant,
    `include(f'{app}.urls')` in a module-level `for app in [...]` loop (the loop's text for the variable), and
    `include(module)` in a route helper or list builder (the text its call gives the parameter). A path that does not
    resolve to one literal names no module."""

    def __init__(self, names, values):
        self._names = names  # NameLookup
        self._text = BoundText(values)

    def module(self, scope, node, given):
        """The file of the module `node` names, read in `scope` with `given` {name: text}; or None."""
        text = self._text.text(scope, node, given)
        return self._names.dotted_module(text) if text else None
