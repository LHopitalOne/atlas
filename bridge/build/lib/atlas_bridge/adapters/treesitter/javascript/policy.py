"""Which javascript / typescript code is test code: by path (spec and test files, __tests__) or inside a test block."""

from ..kit import TestPathPolicy
from .syntax.nodes import JsSyntax


class JavaScriptTestPolicy(TestPathPolicy):
    """The shared path rules (`*.spec.ts`, `*.test.js`, `__tests__/`, `__mocks__/`...), plus code inside the blocks
    of a test framework (`describe(...)`, `it(...)`, `beforeEach(...)`), wherever the file is."""

    TEST_FUNCS = frozenset({'describe', 'it', 'test', 'beforeEach', 'beforeAll', 'afterEach', 'afterAll', 'suite'})

    def in_test_block(self, node):
        """The node is inside the callback of a test framework call, wherever the file is."""
        n = node.parent
        while n is not None:
            if n.type == 'call_expression' and self._is_test_call(n):
                return True
            n = n.parent
        return False

    @classmethod
    def _is_test_call(cls, call):
        return JsSyntax.callee_head(call.child_by_field_name('function')) in cls.TEST_FUNCS
