"""Scopes: which declaration or parameter a name refers to at a point of a file."""

from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax
from .binding import Binding, ParamBinding, ValueBinding


class Scopes:
    """The const/let/var declarations and parameters of one file. Each scope's names are read once and kept."""

    BLOCKS = frozenset({'statement_block', 'program'})
    BINDERS = Functions.FUNCTIONS | {'for_in_statement', 'catch_clause'}  # nodes that bind names without a declaration
    DEFAULTED = frozenset({'assignment_pattern', 'object_assignment_pattern'})
    NAMES = frozenset({'identifier', 'shorthand_property_identifier_pattern'})
    PATTERNS = frozenset({'object_pattern', 'array_pattern', 'rest_pattern'})

    def __init__(self):
        self._blocks = {}  # block node id -> {name: Binding}
        self._params = {}  # binder node id -> {name: parameter node}

    def lookup(self, node, name):
        """The initializer of the const/let/var `name` visible from `node`; None if a parameter shadows it."""
        binding = self.binding(node, name)
        return binding.initializer if binding is not None else None

    def binding(self, node, name) -> Binding | None:
        """The nearest binding of `name` around `node`, or None when nothing in the file binds it."""
        scope = node.parent
        while scope is not None:
            if scope.type in self.BLOCKS:
                found = self._declared(scope).get(name)
                if found is not None and found.node.id != node.id and not JsSyntax.contains(found.node, node):
                    return found
            elif scope.type in self.BINDERS:
                param = self._parameters(scope).get(name)
                if param is not None:
                    return ParamBinding(param)
            scope = scope.parent
        return None

    def _declared(self, block):
        found = self._blocks.get(block.id)
        if found is None:
            found = {}
            for child in block.named_children:
                if child.type == 'export_statement':
                    child = child.child_by_field_name('declaration') or child
                if child.type in JsSyntax.DECLARATIONS:
                    self._declare(found, child)
            self._blocks[block.id] = found
        return found

    def _declare(self, found, declaration):
        for d in declaration.named_children:
            name, value = d.child_by_field_name('name'), d.child_by_field_name('value')
            if value is None or name is None:
                continue
            if name.type == 'identifier':
                found.setdefault(JsSyntax.text(name), ValueBinding(value))
            else:  # const {api} = props
                found.update((n, ParamBinding(d)) for n in self.pattern_names(name) if n not in found)

    def _parameters(self, node):
        """{name: parameter node} for a function's parameters, a for-in/of variable or a catch parameter."""
        found = self._params.get(node.id)
        if found is None:
            found = {}
            for p in self._parameter_nodes(node):
                for name in self.pattern_names(p):
                    found.setdefault(name, p)
            self._params[node.id] = found
        return found

    @staticmethod
    def _parameter_nodes(node):
        if node.type == 'for_in_statement':
            return [node.child_by_field_name('left')]
        if node.type == 'catch_clause':
            return [node.child_by_field_name('parameter')]
        single = node.child_by_field_name('parameter')
        formal = node.child_by_field_name('parameters')
        return [single] if single is not None else (formal.named_children if formal is not None else [])

    @classmethod
    def pattern_names(cls, node):
        """Names a parameter or pattern binds (not the names in its default values)."""
        if node is None:
            return []
        if node.type in JsSyntax.PARAMETERS:
            node = node.child_by_field_name('pattern')
        elif node.type in cls.DEFAULTED:
            node = node.child_by_field_name('left')
        elif node.type == 'pair_pattern':
            node = node.child_by_field_name('value')
        if node is None:
            return []
        if node.type in cls.NAMES:
            return [JsSyntax.text(node)]
        if node.type in cls.PATTERNS:
            return [n for c in node.named_children for n in cls.pattern_names(c)]
        return []
