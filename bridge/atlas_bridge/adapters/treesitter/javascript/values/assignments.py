"""The values a `let` / `var` variable may hold where it is read: its initializer and the values assigned to it
before that point (`let url = '/a/' + id; if (c) url = '/b/' + id; fetch(url)`)."""

from ..syntax.functions import Functions
from ..syntax.nodes import JsSyntax


class Assignments:
    """Reads the assignments of the variables of one file (each block's assignments are found once). A name that is
    not a `let` / `var` of this file, or one that is changed in place (`url += '/x'`), has only the value it reads
    as."""

    NAMES = frozenset({'identifier', 'shorthand_property_identifier'})
    BLOCKS = frozenset({'statement_block', 'program'})
    REASSIGNABLE = frozenset({'let', 'var'})
    ASSIGN = 'assignment_expression'
    UPDATES = frozenset({'augmented_assignment_expression', 'update_expression'})
    MAX_VALUES = 8  # values one variable is read as

    def __init__(self):
        self._by_scope = {}  # block node id -> {name: [assignment or update nodes]}

    def values(self, node) -> list:
        """The expressions `node` may hold where it is read: [node] itself unless it names a variable assigned
        more than once before that point."""
        node = JsSyntax.unwrap(node)
        if node is None or node.type not in self.NAMES:
            return [node]
        name = JsSyntax.text(node)
        declarator = self._declarator(node, name)
        if declarator is None:
            return [node]
        initial = declarator.child_by_field_name('value')
        found = [initial] if initial is not None else []
        scope = self._scope(declarator)
        for n in self._assignments(scope).get(name, ()):
            if n.start_byte >= node.start_byte or not self._same(n, name, declarator):
                continue
            right = n.child_by_field_name('right')
            if n.type != self.ASSIGN or self._reads(right, name, declarator):
                return [node]  # changed in place (`url += x`, `url = url + x`): none of the values is the whole URL
            if self._unconditional(n, scope):
                found = []  # a statement of the variable's own block: the earlier values are gone by the read
            found.append(right)
        return found[: self.MAX_VALUES] if found and found != [initial] else [node]

    def _assignments(self, scope):
        """{name: the assignments and updates of that name} under a block."""
        found = self._by_scope.get(scope.id)
        if found is None:
            found = self._by_scope[scope.id] = {}
            for n in JsSyntax.walk(scope, {self.ASSIGN, *self.UPDATES}):
                left = self._target(n)
                if left is not None and left.type == 'identifier':
                    found.setdefault(JsSyntax.text(left), []).append(n)
        return found

    @classmethod
    def _reads(cls, right, name, declarator):
        """The assigned value reads the variable itself."""
        return any(
            JsSyntax.text(i) == name and cls._same_name(i, name, declarator)
            for i in JsSyntax.walk(right, {'identifier'})
        )

    @staticmethod
    def _unconditional(n, scope):
        """The assignment is a statement of the block the variable is declared in (no branch or loop around it)."""
        statement = n.parent
        return statement is not None and statement.type == 'expression_statement' and statement.parent.id == scope.id

    @classmethod
    def _same_name(cls, identifier, name, declarator):
        found = cls._declarator(identifier, name)
        return found is not None and found.id == declarator.id

    @staticmethod
    def _target(n):
        return JsSyntax.unwrap(n.child_by_field_name('left') or n.child_by_field_name('argument'))

    @classmethod
    def _same(cls, n, name, declarator):
        """The assignment is to the variable of `declarator` (not to another one of the same name)."""
        return cls._same_name(cls._target(n), name, declarator)

    @classmethod
    def _declarator(cls, node, name):
        """The nearest `let` / `var` declarator of `name` around `node` (None when a parameter, a const or nothing
        in the file binds it)."""
        scope = node.parent
        while scope is not None:
            if scope.type in cls.BLOCKS:
                found = cls._declared(scope, name)
                if found is not None:
                    return found if cls._kind(found) in cls.REASSIGNABLE else None
            elif scope.type in Functions.FUNCTIONS and name in cls._params(scope):
                return None
            scope = scope.parent
        return None

    @staticmethod
    def _declared(block, name):
        for child in block.named_children:
            if child.type == 'export_statement':
                child = child.child_by_field_name('declaration') or child
            if child.type not in JsSyntax.DECLARATIONS:
                continue
            for d in child.named_children:
                target = d.child_by_field_name('name')
                if target is not None and target.type == 'identifier' and JsSyntax.text(target) == name:
                    return d
        return None

    @staticmethod
    def _kind(declarator):
        declaration = declarator.parent
        return JsSyntax.text(declaration.children[0]) if declaration is not None and declaration.children else ''

    @staticmethod
    def _params(fn):
        params = fn.child_by_field_name('parameters') or fn.child_by_field_name('parameter')
        return {JsSyntax.text(n) for n in JsSyntax.walk(params, {'identifier'})} if params is not None else set()

    @staticmethod
    def _scope(declarator):
        """The block the variable lives in (assignments in nested functions are found too)."""
        n = declarator.parent
        while n is not None and n.type not in Assignments.BLOCKS:
            n = n.parent
        return n
