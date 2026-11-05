"""A condition over a wrapper's parameters, evaluated with the arguments of one call site."""

from ..syntax import PythonSyntax


class Condition:
    """Evaluates `x is None`, `not x`, `a and b`, `a or b` and bare parameters with the arguments one call site binds
    (else the parameters' defaults). truth() is True, False, or None when the call site does not decide it."""

    FALSY = ('none', 'false')
    NUMBERS = ('integer', 'float')
    CONTAINERS = ('string', 'concatenated_string', 'list', 'tuple', 'dictionary', 'set')
    DELIMITERS = ('string_start', 'string_end')
    IDENTITY = ('is', 'is not')
    HANDLERS = {
        'parenthesized_expression': '_parenthesized',
        'not_operator': '_not',
        'boolean_operator': '_boolean',
        'comparison_operator': '_comparison',
        'identifier': '_identifier',
    }

    def __init__(self, bound, defaults):
        self._bound = bound  # parameter name -> argument node at this call site
        self._defaults = defaults  # parameter name -> default node or None

    @staticmethod
    def over(test, params):
        """Whether a condition reads only the function's parameters, so a call site's arguments can decide it."""
        names = PythonSyntax.identifiers(test) if test is not None else set()
        return bool(names) and names <= params

    def truth(self, node):
        handler = self.HANDLERS.get(node.type)
        return getattr(self, handler)(node) if handler else None

    def _argument(self, name):
        """(known, node): the argument bound to a parameter, else its default (node None: no value)."""
        if name in self._bound:
            return True, self._bound[name]
        if name in self._defaults:
            return self._defaults[name] is not None, self._defaults[name]
        return False, None

    @classmethod
    def literal_truth(cls, node):
        """Truth of an argument: literals by value; any other expression counts as a supplied, truthy value."""
        t = node.type
        if t in cls.FALSY:
            return False
        if t in cls.NUMBERS:
            return PythonSyntax.text(node).strip('0.') != ''
        if t in cls.CONTAINERS:
            return any(c.type not in cls.DELIMITERS for c in node.named_children)
        return True

    def _parenthesized(self, node):
        return self.truth(node.named_children[0]) if node.named_children else None

    def _not(self, node):
        v = self.truth(node.child_by_field_name('argument'))
        return None if v is None else not v

    def _boolean(self, node):
        a = self.truth(node.child_by_field_name('left'))
        b = self.truth(node.child_by_field_name('right'))
        if PythonSyntax.text(node.child_by_field_name('operator')) == 'and':
            return False if False in (a, b) else (True if a and b else None)
        return True if True in (a, b) else (False if a is False and b is False else None)

    def _comparison(self, node):
        kids = node.named_children
        op = next((c.type for c in node.children if not c.is_named), '')
        if len(kids) != 2 or kids[1].type != 'none' or kids[0].type != 'identifier' or op not in self.IDENTITY:
            return None
        known, arg = self._argument(PythonSyntax.text(kids[0]))
        if not known:
            return None
        return (arg.type == 'none') != (op == 'is not')

    def _identifier(self, node):
        known, arg = self._argument(PythonSyntax.text(node))
        return self.literal_truth(arg) if known else None
