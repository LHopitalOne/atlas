"""Reading Python syntax trees: call arguments, callees, assignment targets, parameters and statement blocks."""

from ..kit import Syntax


class PythonSyntax(Syntax):
    """Python-specific readings of tree-sitter nodes, on top of the kit's text/line/walk/ancestor."""

    # Blocks whose statements still run at module level.
    MODULE_BLOCKS = frozenset(
        {
            'if_statement',
            'elif_clause',
            'else_clause',
            'try_statement',
            'except_clause',
            'finally_clause',
            'with_statement',
            'block',
        }
    )
    # Definitions that open a scope of their own: a function body is read without descending into them.
    NESTED_SCOPES = frozenset({'function_definition', 'class_definition', 'lambda', 'decorated_definition'})
    PATTERNS = ('pattern_list', 'tuple_pattern')
    SEQUENCES = ('expression_list', 'tuple')
    FUNCTION = ('function_definition',)
    CLASS = ('class_definition',)
    SELF_NAMES = frozenset({'self', 'cls'})  # the receiver parameter of methods and classmethods

    @classmethod
    def args(cls, node):
        """(positional argument nodes, {keyword: value node}) of an argument_list."""
        pos, kw = [], {}
        if node is None or node.type != 'argument_list':
            return pos, kw
        for a in node.named_children:
            if a.type == 'keyword_argument':
                kw[cls.text(a.child_by_field_name('name'))] = a.child_by_field_name('value')
            elif a.type != 'comment':
                pos.append(a)
        return pos, kw

    @classmethod
    def call_args(cls, call):
        return cls.args(call.child_by_field_name('arguments'))

    @classmethod
    def callee(cls, call):
        """The called name: 'get' for `requests.get(...)`, 'f' for `f(...)`, '' for anything else."""
        fn = call.child_by_field_name('function')
        if fn is None:
            return ''
        if fn.type == 'attribute':
            return cls.text(fn.child_by_field_name('attribute'))
        return cls.text(fn) if fn.type == 'identifier' else ''

    @staticmethod
    def receiver(call):
        """The object a method is called on (`requests` in `requests.get(...)`), or None for a plain call."""
        fn = call.child_by_field_name('function')
        return fn.child_by_field_name('object') if fn.type == 'attribute' else None

    @classmethod
    def is_self(cls, node):
        """Whether a node is the name `self` or `cls`."""
        return node is not None and node.type == 'identifier' and cls.text(node) in cls.SELF_NAMES

    @classmethod
    def name(cls, node):
        return cls.text(node.child_by_field_name('name')) if node is not None else ''

    @classmethod
    def targets(cls, left, right):
        """[(name, value node)] an assignment binds; `a = b = value` binds both names (walked without recursion)."""
        lefts = []
        while left is not None and right is not None and right.type == 'assignment':
            lefts.append(left)
            left, right = right.child_by_field_name('left'), right.child_by_field_name('right')
        if lefts:
            inner = cls.targets(left, right)
            value = inner[-1][1] if inner else None
            outer = [(cls.text(n), value) for n in reversed(lefts) if n.type == 'identifier' and value is not None]
            return inner + outer
        if left is None or right is None:
            return []
        if left.type == 'identifier':
            return [(cls.text(left), right)]
        if left.type in cls.PATTERNS and right.type in cls.SEQUENCES:
            ls, rs = left.named_children, right.named_children
            if len(ls) == len(rs):
                return [(cls.text(a), b) for a, b in zip(ls, rs, strict=True) if a.type == 'identifier']
        return []

    @classmethod
    def assignment_targets(cls, node):
        return cls.targets(node.child_by_field_name('left'), node.child_by_field_name('right'))

    @staticmethod
    def docstring(block):
        """The docstring of a module or function body, or None."""
        first = block.named_children[0] if block is not None and block.named_children else None
        doc = first.named_children[0] if first is not None and first.type == 'expression_statement' else None
        return doc if doc is not None and doc.type == 'string' else None

    @classmethod
    def module_statements(cls, node):
        """Statements at module level, including those inside if/try/with blocks."""
        for c in node.children:
            if c.type in cls.MODULE_BLOCKS:
                yield from cls.module_statements(c)
            else:
                yield c

    @classmethod
    def body_nodes(cls, node):
        """Every node under a function body, not descending into nested functions, classes or lambdas."""
        stack = [node]
        while stack:
            n = stack.pop()
            yield n
            for c in reversed(n.children):
                if c.type not in cls.NESTED_SCOPES:
                    stack.append(c)

    @classmethod
    def params(cls, func):
        """[(name, default node or None)] of a function's positional-or-keyword and keyword-only parameters."""
        out = []
        params = func.child_by_field_name('parameters')
        for p in params.named_children if params is not None else ():
            t = p.type
            if t == 'identifier':
                out.append((cls.text(p), None))
            elif t == 'typed_parameter' and p.named_children and p.named_children[0].type == 'identifier':
                out.append((cls.text(p.named_children[0]), None))
            elif t in ('default_parameter', 'typed_default_parameter'):
                out.append((cls.text(p.child_by_field_name('name')), p.child_by_field_name('value')))
        return out

    @classmethod
    def param_names(cls, func):
        return {p for p, _ in cls.params(func)}

    @classmethod
    def is_method(cls, func):
        """A function defined in a class body and not a staticmethod."""
        parent = func.parent
        decorators = []
        if parent is not None and parent.type == 'decorated_definition':
            decorators = [cls.text(d) for d in parent.children if d.type == 'decorator']
            parent = parent.parent
        in_class = parent is not None and parent.type == 'block' and parent.parent.type == 'class_definition'
        return in_class and not any('staticmethod' in d for d in decorators)

    @classmethod
    def identifiers(cls, node):
        return {cls.text(n) for n in cls.walk(node, ('identifier',))}
