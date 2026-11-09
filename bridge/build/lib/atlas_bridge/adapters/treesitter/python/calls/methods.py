"""The HTTP methods an expression may give, including choices a wrapper's caller decides."""

from .....core.http import ANY
from ..syntax import PythonSyntax
from ..values import Marker
from ..verbs import HttpVerbs
from .condition import Condition


class MethodOptions:
    """Methods an expression may give: 'POST', ANY, a parameter marker, or a choice the caller settles.

    A method chosen by a condition over the function's own parameters (`'POST' if data else 'GET'`, or a parameter
    replaced under `if method is None:`) becomes a choice, decided per call site from its arguments.
    """

    MAX_DEPTH = 8
    MAX_OPTIONS = 2

    def __init__(self, workspace, values):
        self._workspace = workspace
        self._values = values  # PythonValueResolver
        self._choices = []  # (function, condition, then, else) for methods decided per call site

    def options(self, scope, node, depth=0):
        """[method] the expression may give in `scope`, at most MAX_OPTIONS."""
        if node.type == 'parenthesized_expression' and node.named_children and depth < self.MAX_DEPTH:
            return self.options(scope, node.named_children[0], depth + 1)
        if scope.func is not None and depth < self.MAX_DEPTH:
            narrowed = self._narrowed(scope, node, depth)
            if narrowed:
                return narrowed
        out = []
        for v in self._values.resolve(node, scope):
            if v.is_literal and HttpVerbs.method(v.text):
                out.append(v.text.upper())
            elif v.is_param:
                out.append(v.text)
            else:
                out.append(ANY)
        return list(dict.fromkeys(out))[: self.MAX_OPTIONS]

    def _narrowed(self, scope, node, depth):
        """A choice over the function's parameters, or the options of the local a name was assigned; else None."""
        func = scope.func
        params = PythonSyntax.param_names(func)
        if node.type == 'conditional_expression' and len(node.named_children) == 3:
            then, test, other = node.named_children
            if Condition.over(test, params):
                a, b = self.options(scope, then, depth + 1), self.options(scope, other, depth + 1)
                if len(a) == 1 and len(b) == 1:
                    return [self._choice(func, test, a[0], b[0])]
        elif node.type == 'identifier' and PythonSyntax.text(node) in params:
            return self._guarded(scope, node, params, depth)
        elif node.type == 'identifier':  # a local: verb = 'PUT' if upload else 'GET'
            prior = self._workspace.locals.before(scope.source, func, PythonSyntax.text(node), node.start_byte)
            if prior:
                return self.options(scope, prior[-1].value, depth + 1)
        return None

    def _guarded(self, scope, node, params, depth):
        """`if method is None: method = X` before the use: a choice between X and the parameter itself."""
        name = PythonSyntax.text(node)
        prior = self._workspace.locals.before(scope.source, scope.func, name, node.start_byte)
        if len(prior) != 1 or prior[0].augmented:
            return None
        value = prior[0].value
        stmt = PythonSyntax.ancestor(value, ('if_statement', 'function_definition'))
        if stmt is None or stmt.type != 'if_statement':
            return None
        test, body = stmt.child_by_field_name('condition'), stmt.child_by_field_name('consequence')
        inside = body is not None and body.start_byte <= value.start_byte < body.end_byte
        if not inside or not Condition.over(test, params) or name not in PythonSyntax.identifiers(test):
            return None
        then = self.options(scope, value, depth + 1)
        return [self._choice(scope.func, test, then[0], Marker.wrap(name))] if len(then) == 1 else None

    def _choice(self, func, test, then, other):
        self._choices.append((func, test, then, other))
        return Marker.choice(len(self._choices) - 1)

    def decide(self, method, func, bound, defaults):
        """A choice settled by one call site's arguments: the branch it takes, or ANY when that is not known."""
        condition = Condition(bound, defaults)
        for _ in range(self.MAX_DEPTH):
            if not Marker.is_choice(method):
                return method
            owner, test, then, other = self._choices[Marker.choice_index(method)]
            truth = condition.truth(test) if owner == func else None
            if truth is None:
                return ANY
            method = then if truth else other
        return ANY

    def is_method_arg(self, scope, node):
        """Whether an argument is an HTTP method: a method literal, or a parameter named like one."""
        for v in self._values.resolve(node, scope):
            if v.is_literal and HttpVerbs.method(v.text):
                return True
            if v.is_param and 'method' in v.text:
                return True
        return False
