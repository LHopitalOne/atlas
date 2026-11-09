"""The branches a call sits in, when a wrapper's caller decides them: `if method == 'POST': post() else: get()`."""

from typing import NamedTuple

from ..syntax import PythonSyntax
from .condition import Condition


class Guard(NamedTuple):
    """A condition over a function's parameters and the truth it must have for the guarded call to run."""

    func: object
    test: object
    expected: bool


class Guards:
    """Collects a call's guards inside its function, and checks them with the arguments of one call site."""

    @classmethod
    def around(cls, scope, node) -> tuple:
        """The guards of the if/elif/else branches around `node`, up to its function, whose conditions read only the
        function's parameters."""
        func = scope.func
        if func is None:
            return ()
        params = PythonSyntax.param_names(func)
        out, child, parent = [], node, node.parent
        while parent is not None and parent != func:
            if parent.type == 'if_statement':
                branch = cls._branch(parent, child)
                out += [Guard(func, test, truth) for test, truth in branch if Condition.over(test, params)]
            child, parent = parent, parent.parent
        return tuple(out)

    @staticmethod
    def _branch(stmt, child):
        """[(condition, truth)] that put `child` (the if's consequence or one of its alternatives) on its path."""
        tests = [stmt.child_by_field_name('condition')]
        if child == stmt.child_by_field_name('consequence'):
            return [(tests[0], True)]
        for alt in stmt.children_by_field_name('alternative'):
            test = alt.child_by_field_name('condition') if alt.type == 'elif_clause' else None
            if alt == child:
                return [(t, False) for t in tests] + ([(test, True)] if test is not None else [])
            if test is not None:
                tests.append(test)
        return []

    @staticmethod
    def allow(guards, func, bound, defaults) -> bool:
        """False when a call site's arguments take a branch other than the one a guard of `func` needs."""
        condition = Condition(bound, defaults)
        return all(condition.truth(g.test) in (None, g.expected) for g in guards if g.func == func)
